use std::{
    cmp::max,
    fs::{self, OpenOptions},
    io::Write,
    net::IpAddr,
    path::{Path, PathBuf},
};

use anyhow::{bail, Context, Result};
use clap::Parser;
use rcgen::{
    date_time_ymd, BasicConstraints, Certificate, CertificateParams, DistinguishedName, DnType,
    ExtendedKeyUsagePurpose, IsCa, KeyUsagePurpose, SanType,
};
use serde::Deserialize;

const BASE_YEAR: i32 = 2024;

#[derive(Parser)]
#[command(author, version, about = "Bootstrap PKI cho Opus GPU control-plane", long_about = None)]
struct Cli {
    /// Đường dẫn file cấu hình YAML
    #[arg(short, long, default_value = "security/pki/config.yaml")]
    config: PathBuf,

    /// Cho phép ghi đè nếu file đích đã tồn tại
    #[arg(long)]
    overwrite: bool,
}

#[derive(Debug, Deserialize)]
struct Config {
    #[serde(default = "default_output_dir")]
    output_dir: PathBuf,
    #[serde(default = "default_ca_config")]
    ca: CaConfig,
    services: Vec<ServiceConfig>,
}

#[derive(Debug, Deserialize)]
struct CaConfig {
    common_name: String,
    #[serde(default = "default_ca_validity_days")]
    validity_days: u32,
    #[serde(default)]
    organization: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ServiceConfig {
    name: String,
    #[serde(default)]
    common_name: Option<String>,
    #[serde(default)]
    hosts: Vec<String>,
    #[serde(default)]
    ip_addresses: Vec<String>,
    #[serde(default)]
    organization: Option<String>,
    #[serde(default)]
    validity_days: Option<u32>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let contents = fs::read_to_string(&cli.config)
        .with_context(|| format!("không đọc được file cấu hình: {}", cli.config.display()))?;
    let config: Config = serde_yaml::from_str(&contents)
        .with_context(|| format!("cấu hình PKI không hợp lệ: {}", cli.config.display()))?;

    if config.services.is_empty() {
        bail!("danh sách service trống, không có chứng chỉ nào để cấp");
    }

    let ca = build_ca(&config.ca)?;
    let ca_dir = config.output_dir.join("ca");
    fs::create_dir_all(&ca_dir)
        .with_context(|| format!("không tạo được thư mục CA: {}", ca_dir.display()))?;

    let ca_cert_pem = ca.serialize_pem()?;
    let ca_key_pem = ca.serialize_private_key_pem();
    write_file(&ca_dir.join("root-ca.pem"), &ca_cert_pem, cli.overwrite)?;
    write_private_key(&ca_dir.join("root-ca-key.pem"), &ca_key_pem, cli.overwrite)?;

    for service in &config.services {
        issue_service_cert(&config, service, &ca, &ca_cert_pem, cli.overwrite)?;
    }

    println!(
        "Đã tạo CA và {} chứng chỉ dịch vụ trong {}",
        config.services.len(),
        config.output_dir.display()
    );

    Ok(())
}

fn build_ca(config: &CaConfig) -> Result<Certificate> {
    let mut params = CertificateParams::new(vec![]);
    params.alg = &rcgen::PKCS_ECDSA_P256_SHA256;
    params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
    params.key_usages = vec![
        KeyUsagePurpose::KeyCertSign,
        KeyUsagePurpose::CrlSign,
        KeyUsagePurpose::DigitalSignature,
    ];
    params.not_before = date_time_ymd(BASE_YEAR, 1, 1);
    let not_after_year = compute_not_after_year(config.validity_days, BASE_YEAR);
    params.not_after = date_time_ymd(not_after_year, 1, 1);

    let mut dn = DistinguishedName::new();
    dn.push(DnType::CommonName, config.common_name.as_str());
    if let Some(org) = &config.organization {
        dn.push(DnType::OrganizationName, org.as_str());
    }
    params.distinguished_name = dn;

    Certificate::from_params(params).context("không tạo được chứng chỉ CA")
}

fn issue_service_cert(
    config: &Config,
    service: &ServiceConfig,
    ca: &Certificate,
    ca_pem: &str,
    overwrite: bool,
) -> Result<()> {
    let cn = service
        .common_name
        .clone()
        .unwrap_or_else(|| format!("{}.svc.cluster.local", service.name));

    let mut params = if service.hosts.is_empty() {
        CertificateParams::new(vec![cn.clone()])
    } else {
        CertificateParams::new(service.hosts.clone())
    };
    params.alg = &rcgen::PKCS_ECDSA_P256_SHA256;
    params.is_ca = IsCa::NoCa;
    params.key_usages = vec![
        KeyUsagePurpose::DigitalSignature,
        KeyUsagePurpose::KeyEncipherment,
        KeyUsagePurpose::KeyAgreement,
    ];
    params.extended_key_usages = vec![
        ExtendedKeyUsagePurpose::ServerAuth,
        ExtendedKeyUsagePurpose::ClientAuth,
    ];
    params.not_before = date_time_ymd(BASE_YEAR, 1, 1);
    let validity_days = service.validity_days.unwrap_or(365);
    let not_after_year = compute_not_after_year(validity_days, BASE_YEAR);
    params.not_after = date_time_ymd(not_after_year, 1, 1);

    for ip in &service.ip_addresses {
        let parsed: IpAddr = ip.parse().with_context(|| {
            format!(
                "địa chỉ IP `{ip}` không hợp lệ cho service {}",
                service.name
            )
        })?;
        params.subject_alt_names.push(SanType::IpAddress(parsed));
    }

    let mut dn = DistinguishedName::new();
    dn.push(DnType::CommonName, cn.as_str());
    if let Some(org) = &service.organization {
        dn.push(DnType::OrganizationName, org.as_str());
    }
    params.distinguished_name = dn;

    let cert = Certificate::from_params(params)
        .with_context(|| format!("không tạo được certificate cho service {}", service.name))?;
    let cert_pem = cert
        .serialize_pem_with_signer(ca)
        .with_context(|| format!("không ký được certificate cho service {}", service.name))?;
    let key_pem = cert.serialize_private_key_pem();

    let service_dir = config.output_dir.join(&service.name);
    fs::create_dir_all(&service_dir)
        .with_context(|| format!("không tạo được thư mục service {}", service.name))?;

    write_file(&service_dir.join("tls.crt"), &cert_pem, overwrite)?;
    write_private_key(&service_dir.join("tls.key"), &key_pem, overwrite)?;
    write_file(&service_dir.join("ca.crt"), ca_pem, overwrite)?;
    let fullchain = format!("{cert_pem}\n{ca_pem}");
    write_file(&service_dir.join("fullchain.pem"), &fullchain, overwrite)?;

    Ok(())
}

fn compute_not_after_year(days: u32, base_year: i32) -> i32 {
    let years = max(1, ((days as i64 + 364) / 365) as i32);
    base_year + years
}

fn write_file(path: &Path, contents: &str, overwrite: bool) -> Result<()> {
    if path.exists() && !overwrite {
        bail!(
            "file {} đã tồn tại, dùng --overwrite nếu muốn ghi đè",
            path.display()
        );
    }

    let mut file = OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(path)
        .with_context(|| format!("không mở được file {} để ghi", path.display()))?;
    file.write_all(contents.as_bytes())
        .with_context(|| format!("ghi file {} thất bại", path.display()))?;
    file.flush()
        .with_context(|| format!("flush file {} thất bại", path.display()))?;
    Ok(())
}

fn write_private_key(path: &Path, contents: &str, overwrite: bool) -> Result<()> {
    write_file(path, contents, overwrite)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(path)
            .with_context(|| format!("không đọc được metadata file {}", path.display()))?
            .permissions();
        perms.set_mode(0o600);
        fs::set_permissions(path, perms)
            .with_context(|| format!("không đặt được quyền 0600 cho {}", path.display()))?;
    }
    Ok(())
}

fn default_output_dir() -> PathBuf {
    PathBuf::from("security/pki")
}

fn default_ca_config() -> CaConfig {
    CaConfig {
        common_name: "Opus GPU Internal Root".to_string(),
        validity_days: default_ca_validity_days(),
        organization: Some("Opus GPU".to_string()),
    }
}

fn default_ca_validity_days() -> u32 {
    3650
}
