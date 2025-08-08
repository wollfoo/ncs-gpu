# CUDA MPO Makefile (local to cuda/)
# Build libmpo.so from mpo_kernel.cu

NVCC       = nvcc
NVCCFLAGS  = -O2 -shared -Xcompiler -fPIC -std=c++14
TARGET     = libmpo.so
SRC        = mpo_kernel.cu

# Detect compute capability; fallback to 75 if not available
CUDA_ARCH  = $(shell nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/\./-/g' | sed 's/-//g')
ifeq ($(CUDA_ARCH),)
    CUDA_ARCH = 75
endif

all: $(TARGET)

# Alias for compatibility (so `make cuda` also builds the .so here)
cuda: $(TARGET)

$(TARGET): $(SRC)
	@echo "Building CUDA MPO library (sm_$(CUDA_ARCH))..."
	$(NVCC) $(NVCCFLAGS) -arch=sm_$(CUDA_ARCH) -o $@ $< -lcuda -lcudart
	@echo "✅ Built $(TARGET)"

install: $(TARGET)
	@echo "Installing MPO library to /opt/hooks ..."
	mkdir -p /opt/hooks
	cp $(TARGET) /opt/hooks/
	@echo "✅ Installed $(TARGET) to /opt/hooks/"

clean:
	rm -f $(TARGET)
	@echo "🧹 Cleaned $(TARGET)"

check-deps:
	@echo "Checking CUDA build dependencies..."
	@which $(NVCC) > /dev/null || (echo "❌ NVCC not found" && exit 1)
	@nvidia-smi >/dev/null 2>&1 || echo "⚠️ nvidia-smi not found; using default arch sm_$(CUDA_ARCH)"
	@echo "✅ Dependencies OK (or defaults applied)"

.PHONY: all cuda install clean check-deps
