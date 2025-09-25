use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc,
    },
};

use anyhow::{anyhow, Context, Result};
use serde::Serialize;
use tokio::{
    io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader},
    net::{tcp::OwnedReadHalf, tcp::OwnedWriteHalf, TcpStream},
    sync::{mpsc, Mutex},
};
use tracing::{debug, trace, warn};

const CHANNEL_CAPACITY: usize = 256;

#[derive(Clone)]
pub struct NatsConnection {
    inner: Arc<NatsInner>,
}

struct NatsInner {
    writer: Mutex<OwnedWriteHalf>,
    subscriptions: Mutex<HashMap<u64, mpsc::Sender<Vec<u8>>>>,
    sid_counter: AtomicU64,
}

pub struct NatsSubscription {
    sid: u64,
    receiver: mpsc::Receiver<Vec<u8>>,
    inner: Arc<NatsInner>,
}

impl NatsConnection {
    pub async fn connect(url: &str, name: &str, auth_token: Option<&str>) -> Result<Self> {
        let stream = TcpStream::connect(url)
            .await
            .with_context(|| format!("không thể kết nối NATS tại {url}"))?;
        stream
            .set_nodelay(true)
            .context("không bật được TCP_NODELAY")?;
        let (read_half, write_half) = stream.into_split();
        let inner = Arc::new(NatsInner {
            writer: Mutex::new(write_half),
            subscriptions: Mutex::new(HashMap::new()),
            sid_counter: AtomicU64::new(1),
        });

        let connection = Self {
            inner: inner.clone(),
        };

        let connect_frame = ConnectFrame {
            verbose: false,
            pedantic: false,
            name,
            lang: "rust",
            version: env!("CARGO_PKG_VERSION"),
            auth_token,
        };
        connection
            .send_command(&format!(
                "CONNECT {}",
                serde_json::to_string(&connect_frame)?
            ))
            .await?;

        // Spawn read loop
        tokio::spawn(read_loop(read_half, inner.clone()));

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

async fn read_loop(read_half: OwnedReadHalf, inner: Arc<NatsInner>) {
    let mut reader = BufReader::new(read_half);
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
    reader: &mut BufReader<OwnedReadHalf>,
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
