/*!
 * Message Bus Module
 *
 * In-process message passing system sử dụng crossbeam channels.
 * Zero-copy messaging với Arc-wrapped data cho shared ownership.
 */

pub mod bus;

pub use bus::MessageBus;

#[allow(unused_imports)]
pub use bus::{MessageBusHandles, Message, SendError, GpuMetrics, MiningTask};
