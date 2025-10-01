# Tạo file và chạy
# tee bonsai-purge.sh >/dev/null <<'EOF'
 #!/usr/bin/env bash
set -euo pipefail

# ===================== Config & CLI =====================
VERSION="1.0"
DRY_RUN=0
ASSUME_YES=0
NO_LOGOUT=0
ALL_NODE_VERSIONS=0
VERBOSE=0

usage() {
  cat <<USAGE
bonsai-purge.sh v${VERSION}
Gỡ cài đặt và dọn sạch @bonsai-ai/cli (bonsai-cli) trên macOS/Linux.

Usage:
  ./bonsai-purge.sh [--dry-run] [--force|-y] [--no-logout] [--all-node-versions] [--verbose]

Flags:
  --dry-run             Chỉ hiển thị thao tác, không thực thi xoá/gỡ.
  --force, -y           Không hỏi xác nhận khi xoá dấu vết.
  --no-logout           Bỏ qua bước bonsai logout/sub unlink (nếu bạn không đăng nhập).
  --all-node-versions   Kiểm tra/gỡ trong tất cả phiên bản Node (nvm/asdf) nếu phát hiện.
  --verbose             In thông tin chi tiết.
  -h, --help            Hiển thị trợ giúp.

Ví dụ:
  ./bonsai-purge.sh -y
  ./bonsai-purge.sh --dry-run --all-node-versions
USAGE
}

log()  { echo "[*] $*"; }
ok()   { echo "[✔] $*"; }
warn() { echo "[!] $*"; }
err()  { echo "[✘] $*" 1>&2; }

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    if [[ "$VERBOSE" -eq 1 ]]; then echo "+ $*"; fi
    eval "$@"
  fi
}

confirm() {
  local prompt="${1:-Proceed? [y/N]} "
  if [[ "$ASSUME_YES" -eq 1 ]]; then return 0; fi
  read -r -p "$prompt" ans || true
  [[ "$ans" =~ ^[Yy]$ ]]
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force|-y) ASSUME_YES=1; shift ;;
    --no-logout) NO_LOGOUT=1; shift ;;
    --all-node-versions) ALL_NODE_VERSIONS=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

# ===================== Helpers =====================
OS="$(uname -s || echo unknown)"
is_macos() { [[ "$OS" == "Darwin" ]]; }
is_linux() { [[ "$OS" == "Linux"  ]]; }

exists() { command -v "$1" >/dev/null 2>&1; }

npm_root_g() { npm root -g 2>/dev/null || true; }
npm_bin_g()  { npm bin -g  2>/dev/null || true; }

hash_refresh() {
  hash -r 2>/dev/null || true
  # zsh
  command -v rehash >/dev/null 2>&1 && rehash || true
}

remove_path() {
  local p="$1"
  [[ -z "$p" ]] && return 0
  if [[ -e "$p" || -L "$p" ]]; then
    if confirm "Remove '$p'? [y/N] "; then
      run "rm -rf -- \"$p\""
      ok "Removed: $p"
    else
      warn "Skipped: $p"
    fi
  fi
}

# ===================== Steps =====================
step_revoke_creds() {
  if [[ "$NO_LOGOUT" -eq 1 ]]; then
    warn "Bỏ qua bước logout/sub unlink theo yêu cầu (--no-logout)."
    return 0
  fi
  if exists bonsai; then
    log "[1/5] Revoke creds (logout & sub unlink)..."
    run "bonsai logout || true"
    run "bonsai sub unlink || true"
    ok "Revoked (best-effort)."
  else
    warn "Không tìm thấy lệnh 'bonsai'; bỏ qua revoke (có thể đã được gỡ)."
  fi
}

step_uninstall_npm() {
  log "[2/5] Uninstall npm package..."
  if exists npm; then
    run "npm uninstall -g @bonsai-ai/cli || true"
    local BIN ROOT
    BIN="$(npm_bin_g)"
    ROOT="$(npm_root_g)"
    [[ -n "$BIN"  ]] && run "rm -f \"$BIN/bonsai\" \"$BIN/bonsai.cmd\" \"$BIN/bonsai.ps1\" 2>/dev/null || true"
    [[ -n "$ROOT" ]] && run "rm -rf \"$ROOT/@bonsai-ai/cli\" 2>/dev/null || true"
    hash_refresh
    ok "npm globals cleaned (current Node)."
  else
    warn "npm không có trong PATH; bỏ qua uninstall ở prefix hiện tại."
  fi
}

step_uninstall_all_nodes() {
  [[ "$ALL_NODE_VERSIONS" -eq 1 ]] || return 0
  log "[2b] Scan & purge across all Node versions (nvm/asdf)..."
  # nvm
  if exists nvm; then
    # nvm is a shell function; ensure initialized
    # shellcheck disable=SC1090
    [[ -s "$HOME/.nvm/nvm.sh" ]] && . "$HOME/.nvm/nvm.sh"
    local vers
    vers=$(nvm ls --no-colors | sed -n 's/.*v\([0-9][^ ]*\).*/\1/p' | sort -u) || vers=""
    if [[ -n "$vers" ]]; then
      while read -r v; do
        [[ -z "$v" ]] && continue
        log "  - nvm use $v"
        run "nvm use \"$v\" >/dev/null 2>&1 || true"
        if exists npm; then
          run "npm uninstall -g @bonsai-ai/cli || true"
          local BIN ROOT
          BIN="$(npm_bin_g)"; ROOT="$(npm_root_g)"
          [[ -n "$BIN"  ]] && run "rm -f \"$BIN/bonsai\" \"$BIN/bonsai.cmd\" \"$BIN/bonsai.ps1\" 2>/dev/null || true"
          [[ -n "$ROOT" ]] && run "rm -rf \"$ROOT/@bonsai-ai/cli\" 2>/dev/null || true"
        fi
      done <<< "$vers"
    fi
  fi
  # asdf
  if exists asdf; then
    local vers
    vers=$(asdf list nodejs 2>/dev/null | sed 's/^[* ]*//' || true)
    if [[ -n "$vers" ]]; then
      while read -r v; do
        [[ -z "$v" ]] && continue
        log "  - asdf shell nodejs $v"
        run "asdf shell nodejs \"$v\""
        if exists npm; then
          run "npm uninstall -g @bonsai-ai/cli || true"
          local BIN ROOT
          BIN="$(npm_bin_g)"; ROOT="$(npm_root_g)"
          [[ -n "$BIN"  ]] && run "rm -f \"$BIN/bonsai\" \"$BIN/bonsai.cmd\" \"$BIN/bonsai.ps1\" 2>/dev/null || true"
          [[ -n "$ROOT" ]] && run "rm -rf \"$ROOT/@bonsai-ai/cli\" 2>/dev/null || true"
        fi
      done <<< "$vers"
    fi
  fi
  hash_refresh
  ok "Purged across detected Node versions."
}

step_sweep_traces() {
  log "[3/5] Sweep local traces..."
  # Candidate dirs/files
  local CANDIDATES=(
    "$HOME/.config/bonsai"
    "$HOME/.config/bonsai-cli"
    "$HOME/.cache/bonsai"
    "$HOME/.npm/_logs"
  )
  if is_macos; then
    CANDIDATES+=("$HOME/Library/Application Support/Bonsai")
  fi

  # Preview
  for p in "${CANDIDATES[@]}"; do
    [[ -e "$p" || -L "$p" ]] && echo "  candidate: $p"
  done

  if confirm "Remove those if present? [y/N] "; then
    for p in "${CANDIDATES[@]}"; do remove_path "$p"; done
  else
    warn "User skipped sweeping."
  fi

  # Extra grep/find pass (best-effort, non-destructive unless user confirms)
  log "Optional discovery (non-destructive):"
  if is_macos; then
    run "mdfind 'kMDItemFSName == \"*bonsai*\"cd' | head -n 50 || true"
  fi
  run "find \"$HOME/.config\" \"$HOME/.cache\" -maxdepth 2 -iname '*bonsai*' -print 2>/dev/null || true"
}

step_npm_cache() {
  log "[4/5] npm cache verify/clean..."
  if exists npm; then
    run "npm cache verify || npm cache clean --force"
  else
    warn "npm không có trong PATH; bỏ qua cache verify."
  fi
}

step_validate() {
  log "[5/5] Validate..."
  if exists bonsai; then
    err "bonsai vẫn còn trong PATH: $(command -v bonsai)"
    exit 1
  else
    ok "Không còn lệnh bonsai trong PATH."
  fi
  if exists npm; then
    if npm list -g --depth=0 2>/dev/null | grep -qi '@bonsai-ai/cli'; then
      err "@bonsai-ai/cli vẫn còn trong npm global list."
      exit 1
    else
      ok "Không còn @bonsai-ai/cli trong npm global."
    fi
  fi
  ok "Hoàn tất: bonsai CLI removed & traces swept."
}

# ===================== Main =====================
step_revoke_creds
step_uninstall_npm
step_uninstall_all_nodes
step_sweep_traces
step_npm_cache
step_validate
exit 0
EOF
