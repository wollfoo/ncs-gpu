use app_gpu::{Task, TaskKind};

#[test]
fn json_serde_task() {
    let t = Task::new(TaskKind::Gemm { n: 64, iters: 2 });
    let s = serde_json::to_string(&t).unwrap();
    let _b: Task = serde_json::from_str(&s).unwrap();
}
