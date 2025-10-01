#!/usr/bin/env bash
# Purge Augment/Auggie CLI safely (production-ready)
# - Linux/macOS; systemd steps will no-op on macOS
# - Idempotent; --dry-run supported
set -Eeuo pipefail
IFS=$'\n\t'

DRY=false
ALL_USERS=false
STRIP_ENV=false
BLOCK_NPX=false

usage() {
  cat <<'EOF'
Usage: sudo ./purge-auggie.sh [--all-users] [--strip-env] [--block-npx] [--dry-run] [-h|--help]

Options:
  --all-users   Xoá dấu vết cho mọi user (/home/*, /root) + systemd system (cần sudo/root)
  --strip-env   Gỡ dòng AUGMENT_* và alias 'auggie' khỏi rc files của user và /etc/*
  --block-npx   Thêm alias chặn 'auggie' vào ~/.bashrc & ~/.zshrc (tránh npx tải lại)
  --dry-run     Chạy thử, chỉ in các hành động sẽ thực hiện
  -h, --help    Trợ giúp

Gợi ý:
  - Chạy với sudo để đảm bảo dọn triệt để (npm global của root, /usr/bin, systemd system).
  - Script an toàn để chạy nhiều lần.
EOF
}

log()  { printf '[*] %s\n' "$*"; }
ok()   { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
run()  { $DRY && echo "DRY: $*" || eval "$@"; }

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --all-users) ALL_USERS=true; shift ;;
    --strip-env) STRIP_ENV=true; shift ;;
    --block-npx) BLOCK_NPX=true; shift ;;
    --dry-run)   DRY=true; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) warn "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

require_sudo_if_needed() {
  if $ALL_USERS; then
    if [[ "$(id -u)" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
      warn "--all-users yêu cầu chạy dưới quyền root hoặc có 'sudo'. Hủy."
      exit 3
    fi
  fi
}
require_sudo_if_needed

uninstall_npm() {
  if command -v npm >/dev/null 2>&1; then
    log "npm uninstall (user)"
    run npm uninstall -g @augmentcode/auggie || true
    log "npm cache clean (user)"
    run npm cache clean --force || true
  else
    warn "npm không có trong PATH (user)"
  fi
  if command -v sudo >/dev/null 2>&1; then
    log "npm uninstall (root)"
    run sudo npm uninstall -g @augmentcode/auggie || true
    log "npm cache clean (root)"
    run sudo npm cache clean --force || true
  fi
}

uninstall_yarn_pnpm() {
  if command -v yarn >/dev/null 2>&1; then
    log "yarn global remove"
    run yarn global remove @augmentcode/auggie || true
  fi
  if command -v pnpm >/dev/null 2>&1; then
    log "pnpm remove -g"
    run pnpm remove -g @augmentcode/auggie || true
  fi
}

bin_dirs_candidates() {
  local prefix dirlist=()
  if command -v npm >/dev/null 2>&1; then
    prefix="$(npm prefix -g 2>/dev/null || echo /usr)"
    dirlist+=("$prefix/bin")
  fi
  dirlist+=("$HOME/.local/bin" "/usr/local/bin" "/usr/bin")
  # Unique-ify
  printf "%s\n" "${dirlist[@]}" | awk '!seen[$0]++'
}

remove_binaries() {
  log "Xoá binary/symlink auggie (an toàn, chỉ file/link)"
  local d
  while IFS= read -r d; do
    [[ -d "$d" ]] || continue
    # Chỉ lấy file hoặc symlink tên auggie*
    mapfile -t targets < <(find "$d" -maxdepth 1 \( \( -type f -o -type l \) -a -name 'auggie*' \) -print 2>/dev/null)
    if ((${#targets[@]})); then
      printf '[*] remove from %s:\n' "$d"
      printf '    - %s\n' "${targets[@]}"
      $DRY || rm -f -- "${targets[@]}"
    fi
  done < <(bin_dirs_candidates)
}

remove_user_configs() {
  log "Xoá ~/.augment & cache npx của user hiện tại"
  run rm -rf "$HOME/.augment" || true
  # cache npx
  run rm -rf "$HOME/.npm/_npx" 2>/dev/null || true
  # mọi .augment nằm rải rác trong home
  run find "$HOME" -type d -name ".augment" -prune -exec rm -rf {} + || true
}

remove_all_users_configs() {
  $ALL_USERS || return 0
  log "Xoá config mọi user: /root và /home/*"
  if [[ "$(id -u)" -eq 0 ]]; then
    run rm -rf /root/.augment 2>/dev/null || true
    run bash -lc 'find /home -maxdepth 2 -type d -name ".augment" -prune -exec rm -rf {} +' || true
    # npx cache của root
    run rm -rf /root/.npm/_npx 2>/dev/null || true
  else
    run sudo rm -rf /root/.augment 2>/dev/null || true
    run sudo bash -lc 'find /home -maxdepth 2 -type d -name ".augment" -prune -exec rm -rf {} +' || true
    run sudo rm -rf /root/.npm/_npx 2>/dev/null || true
  fi
}

systemd_cleanup() {
  # user-level
  if command -v systemctl >/dev/null 2>&1; then
    log "Dọn systemd --user (nếu có)"
    run systemctl --user stop auggie.service 2>/dev/null || true
    run systemctl --user disable auggie.service 2>/dev/null || true
    run rm -f "$HOME/.config/systemd/user/auggie.service" 2>/dev/null || true
    run systemctl --user daemon-reload 2>/dev/null || true
  fi
  # system-level
  if $ALL_USERS && command -v systemctl >/dev/null 2>&1; then
    log "Dọn systemd (system) nếu từng cài thủ công"
    if [[ "$(id -u)" -eq 0 ]]; then
      run systemctl stop auggie.service 2>/dev/null || true
      run systemctl disable auggie.service 2>/dev/null || true
      run rm -f /etc/systemd/system/auggie.service 2>/dev/null || true
      run systemctl daemon-reload 2>/dev/null || true
    else
      run sudo systemctl stop auggie.service 2>/dev/null || true
      run sudo systemctl disable auggie.service 2>/dev/null || true
      run sudo rm -f /etc/systemd/system/auggie.service 2>/dev/null || true
      run sudo systemctl daemon-reload 2>/dev/null || true
    fi
  fi
}

sed_inplace_backup() {
  # portable-ish: sed -i.bak then we can remove .bak later
  local file="$1" pattern="$2"
  if [[ -f "$file" ]]; then
    $DRY || cp "$file" "$file.bak.purge-auggie"
    run sed -i.bak.purge-auggie "$pattern" "$file"
  fi
}

strip_env_rc() {
  $STRIP_ENV || return 0
  log "Gỡ AUGMENT_* & alias 'auggie' khỏi rc files (user)"
  # bash/zsh
  for f in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [[ -f "$f" ]] || continue
    sed_inplace_backup "$f" '/AUGMENT_\(SESSION_AUTH\|API_TOKEN\|API_URL\)/d'
    sed_inplace_backup "$f" '/alias \+auggie=/d'
  done
  # fish
  if [[ -f "$HOME/.config/fish/config.fish" ]]; then
    sed_inplace_backup "$HOME/.config/fish/config.fish" '/set -x AUGMENT_\(SESSION_AUTH\|API_TOKEN\|API_URL\)/d'
    sed_inplace_backup "$HOME/.config/fish/config.fish" '/alias \+auggie/d'
  fi

  # /etc scope (requires sudo/root)
  if command -v sudo >/dev/null 2>&1 || [[ "$(id -u)" -eq 0 ]]; then
    for f in /etc/environment /etc/profile; do
      [[ -f "$f" ]] || continue
      if [[ "$(id -u)" -eq 0 ]]; then
        sed_inplace_backup "$f" '/AUGMENT_\(SESSION_AUTH\|API_TOKEN\|API_URL\)/d'
      else
        $DRY || sudo cp "$f" "$f.bak.purge-auggie"
        run sudo sed -i.bak.purge-auggie '/AUGMENT_\(SESSION_AUTH\|API_TOKEN\|API_URL\)/d' "$f"
      fi
    done
    if [[ -d /etc/profile.d ]]; then
      if [[ "$(id -u)" -eq 0 ]]; then
        run bash -lc 'for f in /etc/profile.d/*.sh; do [ -f "$f" ] && sed -i.bak.purge-auggie "/AUGMENT_\|alias \+auggie=/d" "$f"; done' || true
      else
        run sudo bash -lc 'for f in /etc/profile.d/*.sh; do [ -f "$f" ] && sed -i.bak.purge-auggie "/AUGMENT_\|alias \+auggie=/d" "$f"; done' || true
      fi
    fi
  fi
}

block_npx_alias() {
  $BLOCK_NPX || return 0
  log "Thêm alias chặn 'auggie' vào ~/.bashrc & ~/.zshrc"
  for f in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [[ -f "$f" ]] || continue
    if ! grep -qE 'alias[[:space:]]+auggie=' "$f" 2>/dev/null; then
      $DRY && echo "DRY: echo 'alias auggie=\"echo Blocked by policy; return 127\"' >> '$f'" \
           || echo 'alias auggie="echo Blocked by policy; return 127"' >> "$f"
    fi
  done
  # fish
  if [[ -f "$HOME/.config/fish/config.fish" ]]; then
    if ! grep -q 'alias auggie' "$HOME/.config/fish/config.fish" 2>/dev/null; then
      $DRY && echo "DRY: echo 'alias auggie \"echo Blocked by policy; return 127\"' >> ~/.config/fish/config.fish" \
           || echo 'alias auggie "echo Blocked by policy; return 127"' >> "$HOME/.config/fish/config.fish"
    fi
  fi
}

final_checks() {
  echo "=== FINAL CHECKS ==="
  if command -v auggie >/dev/null 2>&1; then
    warn "Still present: $(command -v auggie)"; exit 1
  else
    ok "auggie không còn trong PATH"
  fi

  if command -v npm >/dev/null 2>&1; then
    npm ls -g --depth=0 2>/dev/null | grep -qi augmentcode \
      && warn "npm global (user) còn gói augmentcode" \
      || ok "npm global (user) không còn gói augmentcode"
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo npm ls -g --depth=0 2>/dev/null | grep -qi augmentcode \
      && warn "npm global (root) còn gói augmentcode" \
      || ok "npm global (root) không còn gói augmentcode"
  fi

  [[ -d "$HOME/.augment" ]] && warn "~/.augment vẫn tồn tại" || ok "~/.augment đã xoá"

  if $ALL_USERS; then
    if [[ "$(id -u)" -eq 0 ]]; then
      [[ -d /root/.augment ]] && warn "/root/.augment vẫn tồn tại" || ok "/root/.augment đã xoá"
    else
      sudo test -d /root/.augment && warn "/root/.augment vẫn tồn tại" || ok "/root/.augment đã xoá"
    fi
  fi
}

# --- Execute ---
uninstall_npm
uninstall_yarn_pnpm
remove_binaries
remove_user_configs
remove_all_users_configs
systemd_cleanup
strip_env_rc
block_npx_alias
final_checks

ok "Hoàn tất purge Augment/Auggie."
echo "Gợi ý: mở terminal mới (hoặc 'exec bash -l' / 'exec zsh -l') để nạp lại rc files."
