use std::{net::SocketAddr, path::PathBuf, sync::Arc, time::Duration};

use anyhow::{anyhow, Context};
use audit::{default_audit_path, AuditLogger};
use axum::{
    extract::{ConnectInfo, Path as AxumPath, State},
    http::{HeaderMap, StatusCode},
    routing::{get, post},
    Json, Router,
};
use axum_server::{tls_rustls::RustlsConfig, Handle};
use job_core::{
    DynJobStore, JobError, JobPayload, JobRecord, JobStatus, JobStoreBuilder, JobUpdate,
};
use metrics_exporter_prometheus::PrometheusBuilder;
use nats_lite::{NatsConnection, NatsOptions, NatsTlsConfig};
use once_cell::sync::OnceCell;
use secret_manager::{ChainedSecretProvider, SecretManager, SecretManagerBuilder};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tokio::signal;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use uuid::Uuid;

use self::tls::load_server_config;

#[derive(Clone)]
struct AppState {
    nats: NatsConnection,
    subject: String,
    secret_manager: Arc<SecretManager<ChainedSecretProvider>>,
    bearer_token_key: Option<String>,
    store: DynJobStore,
    audit: AuditLogger,
}

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    service: &'static str,
}

#[derive(Deserialize)]
struct CreateJobRequest {
    payload: serde_json::Value,
}

#[derive(Serialize)]
struct CreateJobResponse {
    id: String,
    status: JobStatus,
}

#[derive(Serialize)]
struct JobDetailsResponse {
    job: JobRecord,
}

#[derive(Debug)]
struct SchedulerConfig {
    http_addr: SocketAddr,
    tls: SchedulerTlsConfig,
    nats_url: String,
    subject: String,
    nats_tls: NatsTlsConfig,
    audit_path: PathBuf,
    secret_refresh: Option<Duration>,
    secret_file_dir: Option<PathBuf>,
    simulated_vault: Option<PathBuf>,
}

#[derive(Debug)]
struct SchedulerTlsConfig {
    cert: PathBuf,
    key: PathBuf,
    client_ca: PathBuf,
}

async fn health_handler() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        service: "scheduler",
    })
}

async fn create_job(
    ConnectInfo(source): ConnectInfo<SocketAddr>,
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(request): Json<CreateJobRequest>,
) -> Result<Json<CreateJobResponse>, StatusCode> {
    state.ensure_authorized(&headers).await?;

    metrics::counter!("scheduler_jobs_received_total").increment(1);
    let job_id = Uuid::new_v4().to_string();
    let payload = match JobPayload::try_from(request.payload) {
        Ok(payload) => payload,
        Err(err) => {
            metrics::counter!("scheduler_jobs_invalid_payload_total").increment(1);
            state
                .audit
                .record_or_warn(&json!({
                    "event": "job_invalid_payload",
                    "job_id": job_id,
                    "source": source.to_string(),
                    "error": err.to_string(),
                }))
                .await;
            error!(error = ?err, "payload không hợp lệ");
            return Err(StatusCode::UNPROCESSABLE_ENTITY);
        }
    };

    let job_record = JobRecord::new(job_id.clone(), payload.clone());
    if let Err(err) = state.store.create_job(job_record.clone()).await {
        metrics::counter!("scheduler_jobs_store_error_total").increment(1);
        state
            .audit
            .record_or_warn(&json!({
                "event": "job_store_error",
                "job_id": job_id,
                "source": source.to_string(),
                "error": err.to_string(),
            }))
            .await;
        error!(error = ?err, job_id = %job_id, "không thể lưu job vào store");
        return Err(status_from_store_error(&err));
    }

    let message = json!({
        "id": job_record.id.clone(),
        "payload": payload,
        "created_at": job_record.created_at,
    });

    let job_bytes = match serde_json::to_vec(&message) {
        Ok(bytes) => bytes,
        Err(err) => {
            error!(error = %err, "không serialize được job message");
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    if let Err(err) = state.nats.publish(&state.subject, &job_bytes).await {
        metrics::counter!("scheduler_jobs_publish_error_total").increment(1);
        error!(error = %err, "không thể publish job tới NATS");
        let update = JobUpdate::failed(format!("publish NATS error: {err}"));
        if let Err(store_err) = state.store.update_job(&job_id, update).await {
            error!(error = ?store_err, job_id = %job_id, "không thể cập nhật trạng thái thất bại");
        }
        state.audit.record_or_warn(&json!({
            "event": "job_publish_failed",
            "job_id": job_id,
            "source": source.to_string(),
            "error": err.to_string(),
        }));
        return Err(StatusCode::BAD_GATEWAY);
    }

    metrics::counter!("scheduler_jobs_published_total").increment(1);
    metrics::histogram!("scheduler_job_payload_bytes").record(job_bytes.len() as f64);
    state.audit.record_or_warn(&json!({
        "event": "job_enqueued",
        "job_id": job_id,
        "source": source.to_string(),
        "payload_bytes": job_bytes.len(),
    }));

    Ok(Json(CreateJobResponse {
        id: job_record.id,
        status: JobStatus::Queued,
    }))
}

async fn get_job(
    ConnectInfo(source): ConnectInfo<SocketAddr>,
    AxumPath(job_id): AxumPath<String>,
    State(state): State<Arc<AppState>>,
) -> Result<Json<JobDetailsResponse>, StatusCode> {
    match state.store.get_job(&job_id).await {
        Ok(Some(record)) => {
            state.audit.record_or_warn(&json!({
                "event": "job_query",
                "job_id": job_id,
                "source": source.to_string(),
                "status": format!("{:?}", record.status),
            }));
            Ok(Json(JobDetailsResponse { job: record }))
        }
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(err) => {
            state.audit.record_or_warn(&json!({
                "event": "job_query_failed",
                "job_id": job_id,
                "source": source.to_string(),
                "error": err.to_string(),
            }));
            error!(error = ?err, job_id = %job_id, "không thể truy vấn job");
            Err(status_from_store_error(&err))
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    init_metrics()?;
    let config = SchedulerConfig::from_env()?;

    let mut secret_builder =
        SecretManagerBuilder::new().with_env_provider(None, config.secret_file_dir.clone());
    if let Some(path) = &config.simulated_vault {
        secret_builder = secret_builder.with_simulated_vault(path.clone());
    }
    if let Some(refresh) = config.secret_refresh {
        secret_builder = secret_builder.with_refresh_interval(refresh);
    }
    let secret_manager = secret_builder.build();

    let audit_logger = AuditLogger::new(&config.audit_path).await?;

    let nats_auth_token = match secret_manager.secret("NATS_AUTH_TOKEN").await {
        Ok(token) => Some(token),
        Err(err) => {
            warn!(error = %err, "không lấy được NATS_AUTH_TOKEN, kết nối sẽ không dùng auth");
            None
        }
    };

    let nats_options = NatsOptions::new(&config.nats_url, "scheduler")
        .auth_token(nats_auth_token.clone())
        .tls(Some(config.nats_tls.clone()));
    let nats = NatsConnection::connect_with_options(nats_options).await?;
    let store = JobStoreBuilder::from_env().build().await?;

    let bearer_token_key = if secret_manager
        .secret("SCHEDULER_BEARER_TOKEN")
        .await
        .is_ok()
    {
        Some("SCHEDULER_BEARER_TOKEN".to_string())
    } else {
        None
    };

    let state = Arc::new(AppState {
        nats,
        subject: config.subject,
        secret_manager: Arc::clone(&secret_manager),
        bearer_token_key,
        store,
        audit: audit_logger.clone(),
    });

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/jobs", post(create_job))
        .route("/jobs/:id", get(get_job))
        .with_state(state);

    info!(address = %config.http_addr, "starting scheduler");

    let shutdown_handle = Handle::new();
    let graceful = shutdown_signal(shutdown_handle.clone());

    let server_config = Arc::new(load_server_config(&config.tls)?);
    let rustls_config = RustlsConfig::from_config(server_config);
    let server = axum_server::bind_rustls(config.http_addr, rustls_config)
        .handle(shutdown_handle.clone())
        .serve(app.into_make_service_with_connect_info::<SocketAddr>())
        .into_future();
    tokio::pin!(server);

    tokio::select! {
        result = &mut server => {
            result?;
        }
        _ = graceful => {
            if let Err(err) = (&mut server).await {
                error!(error = %err, "scheduler server error");
            }
        }
    }

    info!("scheduler stopped");
    Ok(())
}

impl SchedulerConfig {
    fn from_env() -> anyhow::Result<Self> {
        let http_addr: SocketAddr = std::env::var("SCHEDULER_HTTP_ADDR")
            .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
            .parse()?;

        let nats_url = std::env::var("NATS_URL").unwrap_or_else(|_| "127.0.0.1:4222".into());
        let subject = std::env::var("SCHEDULER_SUBJECT").unwrap_or_else(|_| "gpu.jobs".into());

        let audit_path = std::env::var("AUDIT_LOG_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| default_audit_path("scheduler"));

        let secret_refresh = std::env::var("SECRET_REFRESH_INTERVAL_SECS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .map(Duration::from_secs);

        let secret_file_dir = std::env::var("SECRET_FILE_DIR").ok().map(PathBuf::from);
        let simulated_vault = std::env::var("SIMULATED_VAULT_PATH")
            .ok()
            .map(PathBuf::from);

        let nats_tls = build_nats_tls_config(&nats_url)?;
        let tls = build_scheduler_tls_config()?;

        Ok(Self {
            http_addr,
            tls,
            nats_url,
            subject,
            nats_tls,
            audit_path,
            secret_refresh,
            secret_file_dir,
            simulated_vault,
        })
    }
}

impl AppState {
    async fn ensure_authorized(&self, headers: &HeaderMap) -> Result<(), StatusCode> {
        let Some(token_key) = &self.bearer_token_key else {
            return Ok(());
        };

        match self.secret_manager.secret(token_key).await {
            Ok(expected) => {
                let provided = headers
                    .get(axum::http::header::AUTHORIZATION)
                    .and_then(|value| value.to_str().ok());
                let expected_header = format!("Bearer {expected}");
                if provided != Some(expected_header.as_str()) {
                    metrics::counter!("scheduler_jobs_unauthorized_total").increment(1);
                    return Err(StatusCode::UNAUTHORIZED);
                }
                Ok(())
            }
            Err(err) => {
                warn!(error = %err, "không thể tải bearer token từ secret manager");
                Err(StatusCode::INTERNAL_SERVER_ERROR)
            }
        }
    }
}

fn build_nats_tls_config(nats_url: &str) -> anyhow::Result<NatsTlsConfig> {
    let ca_file = PathBuf::from(
        std::env::var("NATS_TLS_CA_FILE")
            .context("cần đặt NATS_TLS_CA_FILE để bật mutual TLS với NATS")?,
    );
    let domain = std::env::var("NATS_TLS_DOMAIN")
        .unwrap_or_else(|_| derive_domain_from_address(nats_url).to_string());
    let client_cert = PathBuf::from(
        std::env::var("NATS_TLS_CLIENT_CERT")
            .context("cần đặt NATS_TLS_CLIENT_CERT cho mutual TLS với NATS")?,
    );
    let client_key = PathBuf::from(
        std::env::var("NATS_TLS_CLIENT_KEY")
            .context("cần đặt NATS_TLS_CLIENT_KEY cho mutual TLS với NATS")?,
    );

    Ok(NatsTlsConfig {
        domain,
        ca_file,
        client_cert: Some(client_cert),
        client_key: Some(client_key),
    })
}

fn build_scheduler_tls_config() -> anyhow::Result<SchedulerTlsConfig> {
    let cert = PathBuf::from(
        std::env::var("SCHEDULER_TLS_CERT").context("cần đặt SCHEDULER_TLS_CERT cho scheduler")?,
    );
    let key = PathBuf::from(
        std::env::var("SCHEDULER_TLS_KEY").context("cần đặt SCHEDULER_TLS_KEY cho scheduler")?,
    );
    let client_ca = PathBuf::from(
        std::env::var("SCHEDULER_TLS_CLIENT_CA")
            .context("cần đặt SCHEDULER_TLS_CLIENT_CA cho scheduler")?,
    );
    Ok(SchedulerTlsConfig {
        cert,
        key,
        client_ca,
    })
}

fn derive_domain_from_address(address: &str) -> String {
    address
        .split(':')
        .next()
        .filter(|s| !s.is_empty())
        .unwrap_or("127.0.0.1")
        .to_string()
}

fn status_from_store_error(err: &JobError) -> StatusCode {
    match err {
        JobError::InvalidPayload(_) => StatusCode::UNPROCESSABLE_ENTITY,
        JobError::NotFound => StatusCode::NOT_FOUND,
        JobError::Redis(_) => StatusCode::BAD_GATEWAY,
        JobError::Serialization(_) | JobError::StoreFailure(_) => StatusCode::INTERNAL_SERVER_ERROR,
    }
}

static PROM_HANDLE: OnceCell<metrics_exporter_prometheus::PrometheusHandle> = OnceCell::new();

fn init_metrics() -> anyhow::Result<()> {
    let addr: SocketAddr = std::env::var("SCHEDULER_METRICS_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:9100".into())
        .parse()?;

    let handle = PrometheusBuilder::new()
        .with_http_listener(addr)
        .install_recorder()?;

    let _ = PROM_HANDLE.set(handle);
    Ok(())
}

async fn shutdown_signal(handle: Handle) {
    if let Err(err) = signal::ctrl_c().await {
        error!("failed to listen for shutdown signal: {err}");
    }
    handle.shutdown();
}

mod tls {
    use std::{fs, io::BufReader, path::Path, sync::Arc};

    use anyhow::{anyhow, Context, Result};
    use rustls::{
        self, server::AllowAnyAuthenticatedClient, Certificate, PrivateKey, RootCertStore,
        ServerConfig,
    };
    use rustls_pemfile::{certs, pkcs8_private_keys, rsa_private_keys};

    use super::SchedulerTlsConfig;

    pub fn load_server_config(tls: &SchedulerTlsConfig) -> Result<ServerConfig> {
        let certs = load_certs(&tls.cert)?;
        let key = load_private_key(&tls.key)?;
        let client_roots = load_root_store(&tls.client_ca)?;
        let verifier = AllowAnyAuthenticatedClient::new(client_roots);

        let mut config = ServerConfig::builder()
            .with_safe_defaults()
            .with_client_cert_verifier(Arc::new(verifier))
            .with_single_cert(certs, key)?;
        config.alpn_protocols = vec![b"h2".to_vec(), b"http/1.1".to_vec()];
        Ok(config)
    }

    fn load_certs(path: &Path) -> Result<Vec<Certificate>> {
        let file = fs::File::open(path)
            .with_context(|| format!("không mở được cert: {}", path.display()))?;
        let mut reader = BufReader::new(file);
        let certs = certs(&mut reader).map_err(|err| anyhow!("đọc cert thất bại: {err}"))?;
        Ok(certs.into_iter().map(Certificate).collect())
    }

    fn load_private_key(path: &Path) -> Result<PrivateKey> {
        let file = fs::File::open(path)
            .with_context(|| format!("không mở được private key: {}", path.display()))?;
        let mut reader = BufReader::new(file);
        if let Some(key) = pkcs8_private_keys(&mut reader)
            .map_err(|err| anyhow!("đọc PKCS#8 key thất bại: {err}"))?
            .into_iter()
            .next()
        {
            return Ok(PrivateKey(key));
        }
        let file = fs::File::open(path)
            .with_context(|| format!("không mở được private key: {}", path.display()))?;
        let mut reader = BufReader::new(file);
        if let Some(key) = rsa_private_keys(&mut reader)
            .map_err(|err| anyhow!("đọc RSA key thất bại: {err}"))?
            .into_iter()
            .next()
        {
            return Ok(PrivateKey(key));
        }
        Err(anyhow!(
            "không tìm thấy private key hợp lệ trong {}",
            path.display()
        ))
    }

    fn load_root_store(path: &Path) -> Result<RootCertStore> {
        let certs = load_certs(path)?;
        let mut store = RootCertStore::empty();
        for cert in certs {
            store
                .add(&cert)
                .map_err(|err| anyhow!("không thêm được CA: {err}"))?;
        }
        Ok(store)
    }
}
