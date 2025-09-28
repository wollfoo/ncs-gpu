pub mod config;
pub mod job;

pub mod version {
    /// Trả về mã phiên bản khung chung để tiện kiểm tra build.
    pub fn current() -> &'static str {
        env!("CARGO_PKG_VERSION")
    }
}
