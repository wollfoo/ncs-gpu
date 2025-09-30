// **[OpenCL Backend]** (hậu phương OpenCL – thực thi kernel GPU)
// Triển khai có điều kiện: chỉ biên dịch khi bật feature "gpu".

use anyhow::Result;

#[cfg(feature = "gpu")]
pub fn run_gemm(n: usize, iters: u32) -> Result<()> {
    use ocl::{Buffer, Kernel, Platform, ProQue};

    let src = include_str!("../../kernels/gemm.cl");
    let platform = Platform::default();
    let pro_que = ProQue::builder()
        .src(src)
        .dims(n * n)
        .platform(platform)
        .build()?;

    // A = ones, B = ones, C = zeros
    let a = Buffer::<f32>::builder().queue(pro_que.queue().clone()).len(n * n).fill_val(1.0f32).build()?;
    let b = Buffer::<f32>::builder().queue(pro_que.queue().clone()).len(n * n).fill_val(1.0f32).build()?;
    let c = Buffer::<f32>::builder().queue(pro_que.queue().clone()).len(n * n).fill_val(0.0f32).build()?;

    let mut k = Kernel::builder()
        .program(&pro_que.program())
        .name("gemm_naive")
        .global_work_size([n, n])
        .arg(&a)
        .arg(&b)
        .arg(&c)
        .arg(&(n as i32))
        .build()?;

    for _ in 0..iters {
        unsafe { k.enq()?; }
        pro_que.queue().finish()?;
    }
    // Optional: read-back one element to enforce completion
    let mut out = vec![0f32; 1];
    c.read(&mut out).offset(0).enq()?;
    Ok(())
}

#[cfg(not(feature = "gpu"))]
pub fn run_gemm(n: usize, iters: u32) -> Result<()> {
    // **[CPU Fallback]** (lùi CPU – chạy mô phỏng khi không có OpenCL)
    let mut c = vec![0f32; n * n];
    let a = vec![1f32; n * n];
    let b = vec![1f32; n * n];
    for _ in 0..iters {
        for i in 0..n {
            for j in 0..n {
                let mut sum = 0f32;
                for k in 0..n {
                    sum += a[i * n + k] * b[k * n + j];
                }
                c[i * n + j] = sum;
            }
        }
    }
    // Không trả giá trị – chỉ mô phỏng tải
    Ok(())
}
