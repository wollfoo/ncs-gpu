use std::{
    collections::HashMap,
    fs,
    io::BufReader,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
};

use anyhow::{anyhow, Context, Result};
use rustls::pki_types::{CertificateDer, PrivateKeyDer, ServerName};
use rustls::{ClientConfig, RootCertStore};
use serde::Serialize;
use tokio::{
    io::{self, AsyncBufReadExt, AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt, BufReader},
    net::TcpStream,
    sync::{mpsc, Mutex},
};
use tokio_rustls::TlsConnector;
use tracing::{debug, trace, warn};

const CHANNEL_CAPACITY: usize = 256;

type BoxedReader = Box<dyn AsyncRead + Send + Unpin>;
type BoxedWriter = Box<dyn AsyncWrite + Send + Unpin>;

#[derive(Clone)]
pub struct NatsConnection {
    inner: Arc<NatsInner>,
}

struct NatsInner {
    writer: Mutex<BoxedWriter>,
    subscriptions: Mutex<HashMap<u64, mpsc::Sender<Vec<u8>>>>,
    sid_counter: AtomicU64,
}

pub struct NatsSubscription {
    sid: u64,
    receiver: mpsc::Receiver<Vec<u8>>,
    inner: Arc<NatsInner>,
}

#[derive(Debug, Clone)]
pub struct NatsTlsConfig {
    pub domain: String,
    pub ca_file: PathBuf,
    pub client_cert: Option<PathBuf>,
    pub client_key: Option<PathBuf>,
}

#[derive(Debug, Clone)]
pub struct NatsOptions {
    pub address: String,
    pub connection_name: String,
    pub auth_token: Option<String>,
    pub tls: Option<NatsTlsConfig>,
}

impl NatsOptions {
    pub fn new(address: impl Into<String>, connection_name: impl Into<String>) -> Self {
        Self {
            address: address.into(),
            connection_name: connection_name.into(),
            auth_token: None,
            tls: None,
        }
    }

    pub fn auth_token(mut self, token: Option<String>) -> Self {
        self.auth_token = token;
        self
    }

    pub fn tls(mut self, tls: Option<NatsTlsConfig>) -> Self {
        self.tls = tls;
        self
    }
}

impl NatsConnection {
    pub async fn connect(url: &str, name: &str, auth_token: Option<&str>) -> Result<Self> {
        let options = NatsOptions::new(url, name).auth_token(auth_token.map(|t| t.to_string()));
        Self::connect_with_options(options).await
    }

    pub async fn connect_with_options(options: NatsOptions) -> Result<Self> {
        let tcp = TcpStream::connect(&options.address)
            .await
            .with_context(|| format!("không thể kết nối NATS tại {}", options.address))?;
        tcp.set_nodelay(true)
            .context("không bật được TCP_NODELAY")?;

        let (reader, writer) = if let Some(tls) = &options.tls {
            let connector = build_tls_connector(tls)?;
            let server_name = ServerName::try_from(tls.domain.as_str())
                .map_err(|_| anyhow!("NATS_TLS_DOMAIN `{}` không hợp lệ", tls.domain))?;
            let tls_stream = connector.connect(server_name, tcp).await?;
            split_stream(StreamKind::Tls(tls_stream))
        } else {
            split_stream(StreamKind::Plain(tcp))
        };

        let inner = Arc::new(NatsInner {
            writer: Mutex::new(writer),
            subscriptions: Mutex::new(HashMap::new()),
            sid_counter: AtomicU64::new(1),
        });

        let connection = Self {
            inner: inner.clone(),
        };

        let connect_frame = ConnectFrame {
            verbose: false,
            pedantic: false,
            name: options.connection_name.as_str(),
            lang: "rust",
            version: env!("CARGO_PKG_VERSION"),
            auth_token: options.auth_token.as_deref(),
        };
        connection
            .send_command(&format!(
                "CONNECT {}",
                serde_json::to_string(&connect_frame)?
            ))
            .await?;

        tokio::spawn(read_loop(reader, inner.clone()));

        connection.send_command("PING").await?;
        Ok(connection)
    }

    pub async fn publish(&self, subject: &str, data: &[u8]) -> Result<()> {
        let mut writer = self.inner.writer.lock().await;
        writer
            .write_all(format!("PUB {} {}\r\n", subject, data.len()).as_bytes())
            .await?;
        writer.write_all(data).await?;
        writer.write_all(b"\r\n").await?;
        writer.flush().await?;
        Ok(())
    }

    pub async fn queue_subscribe(
        &self,
        subject: &str,
        queue_group: &str,
    ) -> Result<NatsSubscription> {
        let sid = self.inner.sid_counter.fetch_add(1, Ordering::Relaxed);
        let (tx, rx) = mpsc::channel(CHANNEL_CAPACITY);

        {
            let mut map = self.inner.subscriptions.lock().await;
            map.insert(sid, tx);
        }

        self.send_command(&format!("SUB {} {} {}", subject, queue_group, sid))
            .await?;
        self.send_command("PING").await?;

        Ok(NatsSubscription {
            sid,
            receiver: rx,
            inner: self.inner.clone(),
        })
    }

    async fn send_command(&self, command: &str) -> Result<()> {
        let mut writer = self.inner.writer.lock().await;
        writer.write_all(command.as_bytes()).await?;
        writer.write_all(b"\r\n").await?;
        writer.flush().await?;
        Ok(())
    }
}

impl NatsSubscription {
    pub async fn next(&mut self) -> Option<Vec<u8>> {
        self.receiver.recv().await
    }
}

impl Drop for NatsSubscription {
    fn drop(&mut self) {
        let inner = self.inner.clone();
        let sid = self.sid;
        tokio::spawn(async move {
            {
                let mut map = inner.subscriptions.lock().await;
                map.remove(&sid);
            }
            if let Err(err) = async {
                let mut writer = inner.writer.lock().await;
                writer
                    .write_all(format!("UNSUB {}\r\n", sid).as_bytes())
                    .await?;
                writer.flush().await?;
                Result::<()>::Ok(())
            }
            .await
            {
                warn!(error = %err, "không thể gửi UNSUB");
            }
        });
    }
}

#[derive(Serialize)]
struct ConnectFrame<'a> {
    verbose: bool,
    pedantic: bool,
    name: &'a str,
    lang: &'a str,
    version: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    auth_token: Option<&'a str>,
}

enum StreamKind {
    Plain(TcpStream),
    Tls(tokio_rustls::client::TlsStream<TcpStream>),
}

fn split_stream(stream: StreamKind) -> (BoxedReader, BoxedWriter) {
    match stream {
        StreamKind::Plain(stream) => {
            let (reader, writer) = io::split(stream);
            (Box::new(reader), Box::new(writer))
        }
        StreamKind::Tls(stream) => {
            let (reader, writer) = io::split(stream);
            (Box::new(reader), Box::new(writer))
        }
    }
}

async fn read_loop(reader: BoxedReader, inner: Arc<NatsInner>) {
    let mut reader = BufReader::new(reader);
    let mut line = String::new();

    loop {
        line.clear();
        let bytes = match reader.read_line(&mut line).await {
            Ok(0) => break,
            Ok(n) => n,
            Err(err) => {
                warn!(error = %err, "đọc frame thất bại");
                break;
            }
        };

        if bytes == 0 {
            break;
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if trimmed.starts_with("PING") {
            if let Err(err) = respond_pong(&inner).await {
                warn!(error = %err, "không thể gửi PONG");
            }
            continue;
        }

        if trimmed.starts_with("MSG ") {
            if let Err(err) = dispatch_msg(trimmed, &mut reader, &inner).await {
                warn!(error = %err, header = trimmed, "không xử lý được MSG");
            }
            continue;
        }

        if trimmed.starts_with("+OK") {
            trace!(frame = trimmed, "+OK");
            continue;
        }

        if trimmed.starts_with("-ERR") {
            warn!(frame = trimmed, "NATS báo lỗi");
            continue;
        }

        debug!(frame = trimmed, "frame không xác định");
    }
}

async fn respond_pong(inner: &Arc<NatsInner>) -> Result<()> {
    let mut writer = inner.writer.lock().await;
    writer.write_all(b"PONG\r\n").await?;
    writer.flush().await?;
    Ok(())
}

async fn dispatch_msg(
    header: &str,
    reader: &mut BufReader<BoxedReader>,
    inner: &Arc<NatsInner>,
) -> Result<()> {
    let mut parts = header.split_whitespace();
    parts.next(); // MSG
    let _subject = parts.next().context("thiếu subject")?;
    let sid_token = parts.next().context("thiếu sid")?;

    let (maybe_reply, size_token) = match (parts.next(), parts.next()) {
        (Some(token1), Some(token2)) => {
            if token2.chars().all(|c| c.is_ascii_digit()) {
                (Some(token1), token2)
            } else {
                (None, token1)
            }
        }
        (Some(token1), None) => (None, token1),
        _ => return Err(anyhow!("không phân tích được header")),
    };

    if maybe_reply.is_some() {
        // reply subject hiện chưa dùng nhưng có thể log nếu cần
    }

    let sid: u64 = sid_token.parse().context("sid không hợp lệ")?;
    let size: usize = size_token.parse().context("size không hợp lệ")?;

    let mut payload = vec![0u8; size];
    reader.read_exact(&mut payload).await?;
    let mut trailer = [0u8; 2];
    reader.read_exact(&mut trailer).await?; // consume CRLF

    let maybe_sender = {
        let map = inner.subscriptions.lock().await;
        map.get(&sid).cloned()
    };

    if let Some(sender) = maybe_sender {
        if sender.send(payload).await.is_err() {
            warn!(sid, "channel đã đóng, xóa subscription");
            let mut map = inner.subscriptions.lock().await;
            map.remove(&sid);
        }
    } else {
        warn!(sid, "không tìm thấy subscription cho sid");
    }

    Ok(())
}

fn build_tls_connector(tls: &NatsTlsConfig) -> Result<TlsConnector> {
    let mut root_store = RootCertStore::empty();
    for cert in load_certificates(&tls.ca_file)? {
        root_store
            .add(cert)
            .map_err(|err| anyhow!("không thêm được CA: {err}"))?;
    }

    let config_builder = ClientConfig::builder()
        .with_safe_defaults()
        .with_root_certificates(root_store);

    let config = if let (Some(cert_path), Some(key_path)) = (&tls.client_cert, &tls.client_key) {
        let cert_chain = load_certificates(cert_path)?;
        let private_key = load_private_key(key_path)?;
        config_builder.with_client_auth_cert(cert_chain, private_key)?
    } else {
        config_builder.with_no_client_auth()
    };

    Ok(TlsConnector::from(Arc::new(config)))
}

fn load_certificates(path: &Path) -> Result<Vec<CertificateDer<'static>>> {
    let file = fs::File::open(path)
        .with_context(|| format!("không mở được cert file: {}", path.display()))?;
    let mut reader = BufReader::new(file);
    let certs =
        rustls_pemfile::certs(&mut reader).map_err(|err| anyhow!("đọc cert thất bại: {err}"))?;
    Ok(certs)
}

fn load_private_key(path: &Path) -> Result<PrivateKeyDer<'static>> {
    let data =
        fs::read(path).with_context(|| format!("không mở được private key: {}", path.display()))?;
    let mut slice = &data[..];
    if let Some(key) = rustls_pemfile::pkcs8_private_keys(&mut slice)
        .map_err(|err| anyhow!("đọc PKCS#8 key thất bại: {err}"))?
        .into_iter()
        .next()
    {
        return Ok(key);
    }

    let mut slice = &data[..];
    if let Some(key) = rustls_pemfile::rsa_private_keys(&mut slice)
        .map_err(|err| anyhow!("đọc RSA key thất bại: {err}"))?
        .into_iter()
        .next()
    {
        return Ok(key);
    }

    Err(anyhow!(
        "không tìm thấy private key hợp lệ trong {}",
        path.display()
    ))
}
