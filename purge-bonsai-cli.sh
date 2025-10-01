#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Revoke creds..."
bonsai logout 2>/dev/null || true
bonsai sub unlink 2>/dev/null || true   # nếu chưa link thì sẽ không có tác dụng

echo "[2/5] Uninstall npm package..."
npm uninstall -g @bonsai-ai/cli || true
BINGLOBAL="$(npm bin -g 2>/dev/null || true)"
[ -n "$BINGLOBAL" ] && rm -f "$BINGLOBAL/bonsai" 2>/dev/null || true
hash -r 2>/dev/null || true; rehash 2>/dev/null || true

echo "[3/5] Sweep local traces (interactive preview)..."
echo ">>> Possible macOS dirs:"
ls -d ~/Library/Application\ Support/*bonsai* 2>/dev/null || true
ls -d ~/.config/*bonsai* 2>/dev/null || true
read -p "Remove those if shown? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] && {
  rm -rf ~/Library/Application\ Support/Bonsai ~/.config/bonsai* 2>/dev/null || true
}

echo "[4/5] npm cache verify..."
npm cache verify || npm cache clean --force

echo "[5/5] Validate..."
if command -v bonsai >/dev/null 2>&1; then
  echo "STILL FOUND: $(command -v bonsai)"; exit 1
else
  echo "OK: bonsai CLI removed."
fi
