# SBOM Secret Checklist

Configure the following repository secrets before enabling SBOM upload:

- `SBOM_REGISTRY_URL` – endpoint where SBOM JSON will be stored (e.g., https://artifacts.example.com/projects/app-gpu/sbom).
- `SBOM_REGISTRY_TOKEN` – bearer token or API key with write access to the registry path.
- `SBOM_ARTIFACT_NAME` (optional) – override the filename stored at the registry (default: `bom.json`).

The CI job `sbom` reads these secrets and calls `tooling/scripts/upload_sbom.sh`. Leave `SBOM_REGISTRY_URL` empty to skip external upload while keeping GitHub artifact storage.
