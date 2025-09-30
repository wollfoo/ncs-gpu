# AGENTS.md (Amp-optimized)
## Windsurf compatibility wrappers
See @docs/windsurf-compat/**/*.md
---

## Language Rules
- **MANDATORY**: Respond in Vietnamese.  
- **WITH EXPLANATION**: Every English term must include a Vietnamese description.
- **Code Comments /document /Logs /Docstrings**: 
Language usage Default: Code comments (comments), log messages (logs), document and docstrings must be in Vietnamese.
- **Standard Syntax**
**[English Term]** (Vietnamese description – function/purpose)

---

## Kiến trúc & Workspace

* **Loại repo**: Monorepo (ví dụ: `apps/web`, `services/*`, `packages/*`).
* **Ngôn ngữ chính**: TypeScript/Node 20+, Python 3.11+, Go 1.22+, (cập nhật theo thực tế).
* **Công cụ quản lý**: pnpm, uv/pip, go, docker, terraform/k8s.
* **Môi trường tối thiểu**: Node 20+, Python 3.11+, Go 1.22+, Docker 24+.

> Khi làm việc ở subtree, **ưu tiên chạy test/build tại chỗ** trước khi sửa rộng hơn.

---

## Lệnh chuẩn (root)

* Cài đặt: `pnpm i`
* Build: `pnpm -r build`
* Test: `pnpm -r test --no-color`
* Lint/Format: `pnpm -r lint && pnpm -r format`
* Dev (web): `pnpm -C apps/web dev`

> Nếu repo của bạn dùng công cụ khác, **thay thế** lệnh tương ứng.

---

## Quy ước code (chung)

* **Commit**: Conventional Commits (`feat:`, `fix:`, `refactor:`…).
* **Style**: Biome/Prettier cho TS/JS; ruff/black cho Python; gofmt/golangci-lint cho Go.
* **Test**: ưu tiên unit trước integration; snapshot test cần lý do rõ.
* **Review**: PR nhỏ, có checklist test/impact; ghi `BREAKING CHANGE` khi cần.

---

## Anti-patterns & Khu vực nguy hiểm

* Không sửa file sinh tự động trong `generated/**`.
* Không commit secrets; dùng `.env.example` + secret manager (SOPS/Vault/GCP Secret Manager).
* Đối với migration DB: phải chạy `pnpm -C services/api migrate:plan && pnpm -C services/api migrate:apply` trong branch riêng + test e2e.
* Không chạy benchmark/fuzz nặng trên CI chung (chi phí cao) — chuyển sang job thủ công.

---

## Quy tắc theo ngữ cảnh (ngôn ngữ/thu mục)

> Dùng **@-mention** để kéo tài liệu vào context khi Amp đụng tệp phù hợp; dùng **YAML front matter** `globs` để ràng buộc phạm vi áp dụng.

See @docs/typescript.md
See @docs/python.md
See @docs/go.md
See @docs/infra.md
See @docs/frontend.md
See @docs/backend.md

---

## Liên quan DevEx & Build

* **Monorepo tool**: nếu dùng Nx/Turbo, yêu cầu chỉ định target/graph trước khi sửa toàn cục.
* **Cache**: bật remote cache nếu có; không phá cache trừ khi lý do rõ.
* **Artifacts**: build ra `dist/` hoặc `build/`; không thay đổi layout nếu không cập nhật CI/CD.

---

## Hướng dẫn khi tạo PR

* Miêu tả tác động (user-facing, perf, security).
* Gắn kế hoạch rollback nếu đụng infra/feature-flag.
* Chạy đủ lệnh test tương ứng subtree (xem mục ngữ cảnh bên dưới).

---

## Phần dành cho từng subtree (đặt thêm **AGENTS.md** trong thư mục con)

> Khi đặt **AGENTS.md** ở `services/api/` hoặc `apps/web/`, Amp sẽ **chỉ nạp** khi bạn làm việc trong vùng đó, giúp **tiết kiệm context**.

### Ví dụ `services/api/AGENTS.md`

```md
# AGENTS.md (services/api)

## Bối cảnh
- Service API TypeScript (Fastify/Nest, cập nhật theo thực tế)

## Lệnh địa phương
- Cài: `pnpm -C services/api i`
- Build: `pnpm -C services/api build`
- Test: `pnpm -C services/api test --no-color`
- Lint: `pnpm -C services/api lint`

## Quy ước & tránh lỗi
- Đừng sửa schema sinh tự động: `services/api/generated/**`.
- Khi chạm router/controller, luôn cập nhật test tương ứng.

See @docs/backend.md
```

### Ví dụ `apps/web/AGENTS.md`

```md
# AGENTS.md (apps/web)

## Bối cảnh
- Frontend Next.js/React (cập nhật theo thực tế)

## Lệnh địa phương
- Dev: `pnpm -C apps/web dev`
- Build: `pnpm -C apps/web build`
- Test: `pnpm -C apps/web test`

## Quy ước & tránh lỗi
- Không sửa file UI sinh tự động trong `apps/web/.next/**`.
- Ưu tiên Component story + visual regression trước khi đổi design system.

See @docs/frontend.md
```

---

# Tài liệu @-mention theo ngôn ngữ/miền

## docs/typescript.md

```md
---
globs:
  - '**/*.ts'
  - '**/*.tsx'
---
# TypeScript Rules
- `strict: true`, cấm `any` (dùng `unknown` + type guard).
- Format bằng Biome/Prettier, kiểm tra `pnpm -r lint` trước commit.
- Ưu tiên Zod/TypeBox cho schema runtime.
- Khi đụng `packages/shared/**`, cập nhật changelog và bump version.
```

## docs/python.md

```md
---
globs:
  - '**/*.py'
---
# Python Rules
- ruff + black; `uv pip compile` (hoặc pip-tools) để lock deps.
- Tách môi trường: `.venv` không commit; dùng Makefile/justfile.
- Unit test bằng pytest; integration cần mark và ít chạy mặc định.
```

## docs/go.md

```md
---
globs:
  - '**/*.go'
---
# Go Rules
- `go fmt`, `golangci-lint run` trước PR.
- Module tách theo `internal/` khi logic dùng nội bộ.
- Test chạy song song: `go test ./... -race -shuffle=on`.
```

## docs/infra.md

```md
---
globs:
  - 'infra/**'
  - '**/*.tf'
  - '.github/workflows/**'
---
# Infra & CI
- Terraform: `terraform fmt -check && terraform validate`.
- K8s: dùng kustomize/helm; không sửa trực tiếp manifest sinh tự động.
- CI: tách job lint/test/build/deploy; dùng cache hợp lý; secrets từ OIDC/Secret Manager.
```

## docs/frontend.md

```md
---
globs:
  - 'apps/web/**'
---
# Frontend
- Storybook/E2E (Playwright/Cypress) cho thay đổi UI lớn.
- Không đụng `.next/**`.
- Kiểm thử a11y cơ bản (axe/aria) khi thêm component mới.
```

## docs/backend.md

```md
---
globs:
  - 'services/**'
---
# Backend
- Logging structured; không in stack trace ra client.
- Migration DB phải có rollback; chạy test e2e trước khi merge.
- Tôn trọng boundary giữa module; không cross-import vòng.
```


