#!/usr/bin/env bash
# Pre-commit guard: block obvious secrets from entering git.
set -euo pipefail
cd "$(dirname "$0")/.."

STAGED=$(git diff --cached --name-only --diff-filter=ACM || true)
[ -z "$STAGED" ] && exit 0

FAIL=0
for f in $STAGED; do
  case "$f" in
    .env.example) continue ;;
    .env*|*.dump|*.sql.gz) echo "BLOCKED: $f must never be committed"; FAIL=1; continue ;;
  esac
  if git show ":$f" | grep -nE '(IBKR_FLEX_TOKEN|PASSWORD|SECRET|TOKEN)\s*=\s*[A-Za-z0-9]{8,}' >/dev/null 2>&1; then
    echo "BLOCKED: $f appears to contain a real credential"
    FAIL=1
  fi
done
exit $FAIL
