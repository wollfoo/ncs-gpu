use serde::Serialize;
use std::sync::Arc;
use tracing::info;

#[derive(Clone)]
pub struct EventEmitter {
    component: Arc<str>,
}

impl EventEmitter {
    pub fn new(component: &str) -> Self {
        Self { component: Arc::from(component) }
    }

    pub fn emit_json<T: Serialize>(&self, event: &str, payload: &T) {
        match serde_json::to_string(payload) {
            Ok(body) => info!(target: "telemetry", component = %self.component, event, body),
            Err(err) => info!(target: "telemetry", component = %self.component, event = "serialize_error", error = %err),
        }
    }
}
