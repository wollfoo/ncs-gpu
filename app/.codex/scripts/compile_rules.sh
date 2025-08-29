#!/usr/bin/env bash
set -euo pipefail

# Compile multiple rule *.md files from .codex/rules into a unified AGENTS.md
# Also emits a machine-readable manifest.json for downstream tooling.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES_DIR="$ROOT_DIR/rules"
OUT_MD="$ROOT_DIR/AGENTS.md"
OUT_MANIFEST="$ROOT_DIR/rules/manifest.json"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

die() { echo "[compile_rules] ERROR: $*" >&2; exit 1; }

[[ -d "$RULES_DIR" ]] || die "Rules directory not found: $RULES_DIR"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# Collect files
mapfile -t files < <(LC_ALL=C find "$RULES_DIR" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | LC_ALL=C sort)

if (( ${#files[@]} == 0 )); then
  die "No .md files found in $RULES_DIR"
fi

# Utility: extract all front matter blocks and flatten key: value into k=v
extract_meta() {
  local f="$1"
  awk '
    BEGIN{in_fm=0}
    /^```/{cb=!cb}
    cb==1 {next}
    /^---$/ { in_fm = !in_fm; next }
    in_fm==1 && $0 ~ /:/ {
      # keep simple key: value pairs
      key=$1; sub(":$","",key)
      $1=""; val=$0; sub(/^ +/ ,"", val)
      gsub(/"/, "\\\"", val)
      printf("%s=%s\n", key, val)
    }
  ' "$f" 2>/dev/null || true
}

# Utility: extract the first H1 heading after any leading front matter
extract_title() {
  local f="$1"
  awk '
    BEGIN{in_fm=0}
    /^```/{cb=!cb}
    cb==1 {next}
    NR==1 && /^---$/ {in_fm=1; next}
    in_fm==1 && /^---$/ {in_fm=0; next}
    # Some files have multiple FM blocks; skip until first heading
    /^---$/ {in_fm=!in_fm; next}
    in_fm==1 {next}
    /^[ ]*# / { sub(/^#+[ ]*/ ,"", $0); print $0; exit }
  ' "$f" 2>/dev/null
}

# Utility: list unique tag blocks like <context_gathering>
extract_tags() {
  local f="$1"
  awk '
    match($0, /<\/?([A-Za-z0-9_\-]+)>/, m) { if(m[1]!="") tags[m[1]]=1 }
    END {
      first=1
      for (t in tags) { if(!first) printf(","); printf("%s", t); first=0 }
    }
  ' "$f" 2>/dev/null
}

# Utility: strip leading front matter blocks from file content
strip_front_matter() {
  local f="$1"
  awk '
    BEGIN{in_fm=0; started=0}
    NR==1 && /^---$/ {in_fm=1; next}
    in_fm==1 && /^---$/ {in_fm=0; next}
    # Some files repeat front matter blocks; strip contiguous leading ones
    started==0 && /^---$/ {in_fm=!in_fm; next}
    in_fm==1 {next}
    { started=1; print }
  ' "$f" 2>/dev/null
}

# Normalize and score files for ordering
meta_tsv="$tmpdir/meta.tsv"
> "$meta_tsv"

for fn in "${files[@]}"; do
  f="$RULES_DIR/$fn"
  title="$(extract_title "$f")"
  [[ -n "$title" ]] || title="${fn%.*}"
  tags="$(extract_tags "$f")"
  # defaults
  priority="normal"
  activation="manual"
  trigger=""
  type=""
  scope=""
  alwaysApply="false"
  # collect meta from all FM blocks
  while IFS='=' read -r k v; do
    case "$k" in
      priority) priority="$v";;
      activation) activation="$v";;
      trigger) trigger="$v";;
      type) type="$v";;
      scope) scope="$v";;
      alwaysApply) alwaysApply="$v";;
    esac
  done < <(extract_meta "$f")

  # ranking
  case "$priority" in
    high|High) pr=1;;
    normal|Normal) pr=2;;
    low|Low) pr=3;;
    *) pr=9;;
  esac
  case "$activation" in
    always_on|always-on|Always_on) ac=1;;
    manual|Manual) ac=2;;
    *) ac=5;;
  esac
  aa=0; [[ "$alwaysApply" =~ ^[Tt]rue$ ]] && aa=0 || aa=1  # alwaysApply=true first

  printf "%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$aa" "$pr" "$ac" "$title" "$fn" "$priority" "$activation" "$trigger" "$type" "$scope" >> "$meta_tsv"
done

# Sort by: alwaysApply asc, priority asc, activation asc, title asc
sort -t $'\t' -k1,1n -k2,2n -k3,3n -k4,4 "$meta_tsv" > "$tmpdir/sorted.tsv"

# Build manifest.json
{
  echo "["
  first=1
  while IFS=$'\t' read -r aa pr ac title fn priority activation trigger type scope; do
    meta_all=$(extract_meta "$RULES_DIR/$fn" | awk '{ printf("\"%s\":\"%s\",", $1, substr($0, index($0,$2))) }' | sed 's/,$//')
    tags="$(extract_tags "$RULES_DIR/$fn")"
    [[ $first -eq 0 ]] && echo ","
    printf '{"file":"rules/%s","title":"%s","priority":"%s","activation":"%s","trigger":"%s","type":"%s","scope":"%s","alwaysApply":"%s","tags":[%s]%s}' \
      "$fn" "${title//"/\"}" "$priority" "$activation" "$trigger" "$type" "$scope" \
      "$(grep -E "^alwaysApply=" <(extract_meta "$RULES_DIR/$fn") | tail -n1 | cut -d= -f2)" \
      "$(awk -v t="$tags" 'BEGIN{n=split(t,a,","); for(i=1;i<=n;i++){gsub(/^[ ]+|[ ]+$/,"",a[i]); if(a[i]!="") printf("\"%s\"%s", a[i], (i<n?",":""))}}')" \
      "$([ -n "$meta_all" ] && printf ',"meta":{%s}' "$meta_all")"
    first=0
  done < "$tmpdir/sorted.tsv"
  echo
  echo "]"
} > "$OUT_MANIFEST"

# Generate AGENTS.md
{
  echo "# AGENTS – Compiled Rules"
  echo
  echo "Generated: $(timestamp)"
  echo "Source: .codex/rules"
  echo
  echo "## Regenerate"
  echo "Run: \`bash .codex/scripts/compile_rules.sh\`"
  echo
  echo "## Machine-Readable Index"
  echo "The following JSON manifest mirrors the sections below for downstream tooling."
  echo
  echo '\`\`\`json'
  cat "$OUT_MANIFEST"
  echo '\`\`\`'
  echo
  echo "## Table of Contents"
  lineno=1
  while IFS=$'\t' read -r aa pr ac title fn priority activation trigger type scope; do
    anchor=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g; s/[ ]\+/-/g')
    printf "- [%s](#%s) — \\`%s\\`\n" "$title" "$anchor" "$fn"
  done < "$tmpdir/sorted.tsv"
  echo
  echo "---"
  echo
  while IFS=$'\t' read -r aa pr ac title fn priority activation trigger type scope; do
    file_path="$RULES_DIR/$fn"
    anchor=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g; s/[ ]\+/-/g')
    echo "## $title"
    echo
    echo "- File: \`rules/$fn\`"
    [[ -n "$priority" ]] && echo "- Priority: $priority"
    [[ -n "$activation" ]] && echo "- Activation: $activation"
    [[ -n "$trigger" ]] && echo "- Trigger: $trigger"
    [[ -n "$type" ]] && echo "- Type: $type"
    [[ -n "$scope" ]] && echo "- Scope: $scope"
    aa_val=$(grep -E "^alwaysApply=" <(extract_meta "$file_path") | tail -n1 | cut -d= -f2 || true)
    [[ -n "$aa_val" ]] && echo "- alwaysApply: $aa_val"
    tags_val="$(extract_tags "$file_path")"
    [[ -n "$tags_val" ]] && echo "- Tags: $(echo "$tags_val" | sed 's/,/, /g')"
    echo
    # Front matter preview
    fm_block=$(awk 'BEGIN{in=0; printed=0} /^```/{cb=!cb} cb==1 {next} /^---$/ { if(in==0){in=1; next} else {in=0; if(printed==0){printed=1; exit}} } in==1 {print}' "$file_path")
    if [[ -n "$fm_block" ]]; then
      echo "### Front Matter"
      echo '\`\`\`yaml'
      echo "$fm_block"
      echo '\`\`\`'
      echo
    fi
    echo "### Content"
    echo
    strip_front_matter "$file_path"
    echo
    echo "---"
    echo
  done < "$tmpdir/sorted.tsv"
} > "$OUT_MD"

echo "[compile_rules] Wrote: $OUT_MD"
echo "[compile_rules] Wrote: $OUT_MANIFEST"

