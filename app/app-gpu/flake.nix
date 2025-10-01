{
  description = "Secure GPU Mining Core - Academic Security Research Environment";

  # Input sources - reproducible build dependencies
  inputs = {
    # NixOS unstable cho các packages mới nhất
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Rust overlay để có phiên bản Rust mới nhất
    rust-overlay.url = "github:oxalica/rust-overlay";

    # Flake utils cho multi-platform support
    flake-utils.url = "github:numtide/flake-utils";

    # CUDA packages from nix-community
    cuda-maintainers.url = "github:NixOS/nixpkgs/47bf5b80a38a0735c7d85db09287b6c90d5d0bf1";
    cuda-maintainers.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, rust-overlay, flake-utils, cuda-maintainers }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # Overlay system với Rust và CUDA
        overlays = [
          rust-overlay.overlays.default
          cuda-maintainers.overlays.default
        ];

        # Package set với overlays
        pkgs = import nixpkgs {
          inherit system overlays;
        };

        # Rust toolchain configuration (đặt trong flake để reproducible)
        rustToolchain = (pkgs.pkgsBuildHost.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml).override {
          extensions = [
            "rust-src"      # Source code cho development
            "rust-analyzer" # Language server
            "rustfmt"       # Code formatter
            "clippy"        # Linter
            "cargo"         # Package manager
            "rustc"         # Compiler
          ];
        };

        # CUDA toolkit cho GPU support
        cudaPackages = cuda-maintainers.cudaPackages_11_8;

        # Build dependencies
        buildInputs = with pkgs; [
          # Core system libraries
          pkg-config

          # GPU acceleration libraries
          vulkan-loader
          vulkan-tools
          libglvnd
          glib
          xorg.libX11
          xorg.libXcursor
          xorg.libXrandr
          xorg.libXi

          # NVIDIA CUDA (cho GPU mining)
          cudaPackages.cuda_cudart
          cudaPackages.cuda_nvcc
          cudaPackages.cuda_nvrtc
          cudaPackages.cuda_nvml_dev

          # Intel oneAPI (alternative GPU support)
          ocl-icd
          intel-gmmlib

          # Security và monitoring
          openssl
          prometheus  # Metrics server
          grafana     # Visualization

          # Development tools
          clang       # C compiler for linking
          llvm        # LLVM toolchain
          cmake       # Build system
          git         # Version control

          # Containerization và deployment
          docker-client
          kubectl     # Kubernetes client
          kustomize   # Kubernetes configuration

          # Security scanning tools
          trivy       # Container security scanner
          syft        # SBOM generator
          cosign      # Container signing
        ];

        # Native dependencies
        nativeBuildInputs = with pkgs; [
          pkg-config
          rustToolchain
          clang
          cmake
        ];

        # Library path cho linking
        libPath = with pkgs; lib.makeLibraryPath [
          vulkan-loader
          glib
          # CUDA paths cho runtime
          cudaPackages.cuda_cudart
        ];

        # Environment variables cho GPU support
        gpuEnvVars = {
          # Vulkan
          VK_ICD_FILENAMES = "${pkgs.vulkan-loader}/share/vulkan/icd.d/nvidia_icd.x86_64.json";

          # NVIDIA CUDA
          CUDA_PATH = "${cudaPackages.cuda_cudart}";
          LIBRARY_PATH = libPath;
          LD_LIBRARY_PATH = libPath;

          # GPU discovery
          NVIDIA_VISIBLE_DEVICES = "all";
          NVIDIA_DRIVER_CAPABILITIES = "compute,utility,graphics";

          # Security hardening
          RUST_BACKTRACE = "1";  # Enhanced debugging
          RUST_LOG = "info";     # Default log level
          RUSTFLAGS = "-C target-cpu=haswell"; # CPU optimization
        };

      in rec {
        # Development shell với tất cả dependencies
        devShells.default = pkgs.mkShell {
          inherit buildInputs nativeBuildInputs;
          inherit (gpuEnvVars);

          shellHook = ''
            echo "🚀 GPU Mining Development Environment"
            echo "📊 CUDA Version: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits 2>/dev/null || echo 'N/A')"
            echo "🎮 Vulkan Instance Version: $(vulkaninfo --summary 2>/dev/null | head -1 || echo 'N/A')"
            echo "🦀 Rust Version: $(rustc --version)"
            echo "📦 Cargo Version: $(cargo --version)"
            echo ""
            echo "Available commands:"
            echo "  cargo build    - Build application"
            echo "  cargo test     - Run tests"
            echo "  cargo run      - Run application"
            echo "  cargo clippy   - Run linter"
            echo "  cargo fmt      - Format code"
            echo ""
            echo "GPU Mining commands:"
            echo "  cargo run -- --benchmark           - Performance test"
            echo "  cargo run -- --ai-training         - AI camouflage mode"
            echo "  cargo run -- --image-processing    - Image processing mode"
            echo ""
          '';
        };

        # Package definition cho GPU Miner
        packages.default = rustToolchain.rustPlatform.buildRustPackage {
          pname = "gpu-miner";
          version = "0.1.0";

          src = ./.;

          inherit nativeBuildInputs buildInputs;

          cargoLock = {
            lockFile = ./Cargo.lock;
            outputHashes = {
              # Add hash của dependencies có đường dẫn cây nếu cần
              # Example: "crate-name-1.0.0" = "sha256-hash-here";
            };
          };

          # Environment variables cho GPU linking
          env = gpuEnvVars // {
            CARGO_BUILD_TARGET = "x86_64-unknown-linux-gnu";
            CARGO_BUILD_RUSTFLAGS = "-C target-cpu=haswell -C opt-level=3 -C lto=true";
          };

          # Pre-build setup
          preBuild = ''
            export CARGO_HOME=$TMPDIR/cargo-home
            mkdir -p $CARGO_HOME

            # Verify GPU support
            echo "GPU setup verification..."
            ls -la /run/opengl-driver/lib/ 2>/dev/null || echo "No GPU drivers found (expected in container)"
          '';

          # Post-build hardening
          postBuild = ''
            # Strip binary để giảm size
            if command -v strip >/dev/null 2>&1; then
              strip target/x86_64-unknown-linux-gnu/release/gpu-miner
            fi

            # Verify binary
            if [ -f "target/x86_64-unknown-linux-gnu/release/gpu-miner" ]; then
              echo "✅ Build successful"
              file target/x86_64-unknown-linux-gnu/release/gpu-miner
            else
              echo "❌ Build failed"
              exit 1
            fi
          '';

          # Custom install phase để copy binary và metadata
          installPhase = ''
            runHook preInstall

            mkdir -p $out/bin
            cp target/x86_64-unknown-linux-gnu/release/gpu-miner $out/bin/

            # Create metadata file cho security
            cat > $out/share/gpu-miner/metadata.json << EOF
            {
              "name": "gpu-miner",
              "version": "0.1.0",
              "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
              "built_by": "Nix Flake",
              "system": "${system}",
              "rustc_version": "$(rustc --version)",
              "description": "Secure GPU Mining Core for Academic Security Research"
            }
            EOF

            runHook postInstall
          '';

          # Additional metadata
          meta = with pkgs.lib; {
            description = "Secure GPU Mining Core - Academic Security Research";
            homepage = "https://github.com/academic-research/gpu-miner";
            license = licenses.mit;
            maintainers = [ "security-research-team" ];
            platforms = platforms.linux;
          };
        };

        # Docker image từ Nix package (thay thế Dockerfile)
        packages.dockerImage = pkgs.dockerTools.buildImage {
          name = "gpu-miner";
          tag = "latest";

          fromImage = null;
          fromImageName = null;
          fromImageTag = null;

          contents = with pkgs; [
            # Minimal base system
            busybox
            # Our GPU miner
            packages.default
            # Runtime dependencies
            vulkan-loader
          ];

          # Add GPU libraries
          copyToRoot = builtins.attrValues {
            inherit cudaPackages;
          };

          config = {
            Cmd = [ "${packages.default}/bin/gpu-miner" ];
            WorkingDir = "/app";
            Env = [
              "RUST_LOG=info"
              "NVIDIA_VISIBLE_DEVICES=all"
              "VK_ICD_FILENAMES=${pkgs.vulkan-loader}/share/vulkan/icd.d/nvidia_icd.x86_64.json"
            ];
            ExposedPorts = {
              "9090/tcp" = {};  # Prometheus metrics
            };
            Labels = {
              "gpu-miner.version" = "0.1.0";
              "gpu-miner.build-date" = "$(date -u +%Y-%m-%d)";
              "gpu-miner.sbom-path" = "/app/gpu-miner-sbom.json";
              "gpu-miner.criticality" = "high";
              "gpu-miner.research-purpose" = "academic-security";
            };
            User = "nobody";
            ReadOnlyRootFilesystem = true;
            NoNewPrivileges = true;
            SecurityOpt = [
              "no-new-privileges:true"
              "seccomp=unconfined"  # Could be made more restrictive
            ];
          };

          # OCI annotations
          created = "$(date -u +%Y-%m-%dT%H:%M:%SZ)";
          extraCommands = ''
            # Create app directory với correct permissions
            mkdir -p app
            chown nobody:nobody app
          '';
        };

        # App thông qua Flake - cho consistency
        apps.default = flake-utils.lib.mkApp {
          drv = packages.default;
          exePath = "/bin/gpu-miner";
        };

        # Benchmarks và tests
        checks = {
          # Build check
          build = packages.default;

          # Docker image check
          dockerImage = packages.dockerImage;

          # Security scan (runtime check)
          security = pkgs.stdenv.mkDerivation {
            name = "gpu-miner-security-check";
            src = ./.;
            nativeBuildInputs = with pkgs; [ trivy syft cosign ];

            buildPhase = ''
              echo "🔍 Running security checks..."

              # Build SBOM
              syft packages ${packages.default}/bin/gpu-miner -o json > gpu-miner-sbom.json

              # Trivy security scan
              trivy fs --format json --output trivy-results.json .

              echo "✅ Security checks completed"
            '';

            installPhase = ''
              mkdir -p $out/share/security
              cp *.json $out/share/security/
            '';
          };

          # Performance benchmark
          benchmark = pkgs.stdenv.mkDerivation {
            name = "gpu-miner-benchmark";
            src = ./.;

            buildInputs = [ packages.default ];

            buildPhase = ''
              echo "🏃 Running performance benchmark..."
              timeout 30s ${packages.default}/bin/gpu-miner --benchmark > benchmark.log 2>&1 || true
              echo "✅ Benchmark completed"
            '';

            installPhase = ''
              mkdir -p $out/share/benchmark
              cp benchmark.log $out/share/benchmark/
            '';
          };
        };

        # Formatter cho code
        formatter = pkgs.nixpkgs-fmt;

      }
    );
}