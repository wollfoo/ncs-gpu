extern "C" __global__ void miner_kernel(float *output, const float *input, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        output[idx] = input[idx] * 42.0f;
    }
}
