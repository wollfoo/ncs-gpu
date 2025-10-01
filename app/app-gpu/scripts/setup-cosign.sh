#!/bin/bash
# Setup Cosign signing cho GPU Mining container images
# Academic Security Research Framework

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
KEY_DIR="${KEY_DIR:-./cosign-keys}"
KEY_ID="${KEY_ID:-gpu-miner-academic}"
ISSUER="${ISSUER:-academic-research.edu}"

# Registry configuration
REGISTRY="${REGISTRY:-ghcr.io/academic-research}"
IMAGE_NAME="${IMAGE_NAME:-gpu-miner}"
TAG="${TAG:-v0.1.0}"

# Validate prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"

    if ! command -v cosign &> /dev/null; then
        echo -e "${RED}❌ Cosign not found. Install with:${NC}"
        echo "curl -L https://github.com/sigstore/cosign/releases/download/v2.2.3/cosign-linux-amd64 -o /usr/local/bin/cosign && chmod +x /usr/local/bin/cosign"
        exit 1
    fi

    if ! command -v docker &> /dev/null && ! command -v podman &> /dev/null; then
        echo -e "${RED}❌ Docker or Podman not found${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites OK${NC}"
}

# Setup keys directory
setup_keys_dir() {
    mkdir -p "$KEY_DIR"
    chmod 700 "$KEY_DIR"
    echo -e "${BLUE}🔐 Keys directory: ${KEY_DIR}${NC}"
}

# Generate Cosign key pair
generate_keypair() {
    echo -e "${BLUE}🔑 Generating Cosign key pair...${NC}"

    local pub_key="${KEY_DIR}/cosign.pub"
    local priv_key="${KEY_DIR}/cosign.key"

    if [ ! -f "$priv_key" ]; then
        cosign generate-key-pair --output-key-prefix "${KEY_DIR}/cosign"

        echo -e "${GREEN}✅ Key pair generated${NC}"

        # Set secure permissions
        chmod 600 "$priv_key"
        chmod 644 "$pub_key"
    else
        echo -e "${YELLOW}⚠️  Key pair already exists${NC}"
    fi

    echo -e "${BLUE}📋 Public key: ${pub_key}${NC}"
    echo -e "${BLUE}🔒 Private key: ${priv_key}${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Securely backup your private key!${NC}"
}

# Initialize Fulcio if using PKI
setup_fulcio() {
    echo -e "${BLUE}🎖️  Setting up Fulcio PKI integration...${NC}"

    # Check if we want PKI-based signing instead of key-based
    echo -e "${GRN}Note: Academic setup will use key-based signing for simplicity${NC}"
    echo "For production, consider Fulcio PKI integration"

    # Configure OIDC for academic auth (if needed)
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        export COSIGN_EXPERIMENTAL=1
        echo -e "${GREEN}✅ OIDC authentication configured${NC}"
    fi
}

# Create signing policy
create_signing_policy() {
    echo -e "${BLUE}📝 Creating signing policy...${NC}"

    local policy_file="${KEY_DIR}/signing-policy.json"

    cat > "$policy_file" << EOF
{
  "apiVersion": "policy.sigstore.dev/v1alpha1",
  "kind": "ClusterImagePolicy",
  "metadata": {
    "name": "gpu-miner-signing-policy"
  },
  "spec": {
    "images": [
      {
        "glob": "${REGISTRY}/${IMAGE_NAME}:*"
      }
    ],
    "authorities": [
      {
        "key": {
          "data": "$(cat ${KEY_DIR}/cosign.pub | tr -d '\n')"
        },
        "attestations": [
          {
            "name": "custom",
            "predicateType": "https://academic-research.edu/gpu-miner/attestation"
          }
        ]
      }
    ]
  }
}
EOF

    echo -e "${GREEN}✅ Signing policy: ${policy_file}${NC}"
}

# Test signing setup
test_signing() {
    echo -e "${BLUE}🧪 Testing signing setup...${NC}"

    # Create a test file to sign
    echo "GPU Miner Academic Security Research - $(date)" > "${KEY_DIR}/test.txt"

    # Sign the test file
    cosign sign-blob \
        --key "${KEY_DIR}/cosign.key" \
        --tlog-upload=false \
        "${KEY_DIR}/test.txt" \
        > "${KEY_DIR}/test.txt.sig"

    # Verify the signature
    cosign verify-blob \
        --key "${KEY_DIR}/cosign.pub" \
        --tlog-upload=false \
        --signature "${KEY_DIR}/test.txt.sig" \
        "${KEY_DIR}/test.txt"

    echo -e "${GREEN}✅ Signing verification successful${NC}"

    # Clean up test files
    rm "${KEY_DIR}/test.txt" "${KEY_DIR}/test.txt.sig"
}

# Generate documentation
generate_docs() {
    echo -e "${BLUE}📖 Generating documentation...${NC}"

    local readme_file="${KEY_DIR}/README.md"

    cat > "$readme_file" << EOF
# GPU Miner Container Signing
## Academic Security Research Framework

This directory contains the cryptographic keys and policies for signing GPU Miner container images.

## Security Classification

- **Purpose**: Academic defensive security research
- **Key Usage**: Image signing for integrity verification
- **Algorithm**: ECDSA P-256 with SHA-256

## Files

\`\`\`
cosign.pub          # Public verification key
cosign.key          # Private signing key (KEEP SECRET!)
signing-policy.json # Sigstore signing policy
README.md          # This documentation
\`\`\`

## Usage

### Sign an Image
\`\`\`bash
export COSIGN_EXPERIMENTAL=true

# Sign with key-based signature
cosign sign --key cosign.key ${REGISTRY}/${IMAGE_NAME}:${TAG}

# Or use keyless (PKI) signing with GitHub Actions
cosign sign ${REGISTRY}/${IMAGE_NAME}:${TAG}
\`\`\`

### Verify an Image
\`\`\`bash
# Verify with public key
cosign verify --key cosign.pub ${REGISTRY}/${IMAGE_NAME}:${TAG}

# Or verify with transparency log
cosign verify ${REGISTRY}/${IMAGE_NAME}:${TAG}
\`\`\`

### Generate Attestation
\`\`\`bash
# Create build attestation
cosign attest --key cosign.key \\
  --predicate attestation.json \\
  --type https://academic-research.edu/gpu-miner/attestation \\
  ${REGISTRY}/${IMAGE_NAME}:${TAG}
\`\`\`

## Attestation Format

See \`signing-policy.json\` for the attestation predicate format used for academic research verification.

## Research Notes

- Keys are generated for academic demonstration only
- Production deployments should use organization-specific key management
- Consider hardware security modules (HSM) for long-term key storage
- Implement key rotation policies for operational security

## Contact

Academic Security Research Team
security-research@academic.edu
EOF

    echo -e "${GREEN}✅ Documentation: ${readme_file}${NC}"
}

# Display summary
display_summary() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${GREEN}🎉 Cosign Setup Complete!${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "1. Securely backup your private key"
    echo "2. Add public key to your registry's trust policy"
    echo "3. Use the signing scripts in CI/CD pipelines"
    echo "4. Regularly rotate keys for security"
    echo ""
    echo -e "${BLUE}Files generated in: ${KEY_DIR}${NC}"
    echo "$(ls -la ${KEY_DIR})"
}

# Main execution
main() {
    echo -e "${BLUE}🚀 GPU Miner Cosign Setup${NC}"
    echo -e "${BLUE}======================================${NC}"

    check_prerequisites
    setup_keys_dir
    generate_keypair
    setup_fulcio
    create_signing_policy
    test_signing
    generate_docs
    display_summary
}

# Run main với error handling
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi