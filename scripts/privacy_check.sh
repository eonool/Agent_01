#!/usr/bin/env bash
# Fails if any tracked file contains a term listed in the PRIVACY_DENYLIST secret
# (comma-separated, configured in GitHub repo secrets so the names themselves stay private).
set -euo pipefail
if [[ -z "${PRIVACY_DENYLIST:-}" ]]; then
  echo "PRIVACY_DENYLIST not set; skipping."
  exit 0
fi
IFS=',' read -ra TERMS <<< "$PRIVACY_DENYLIST"
for t in "${TERMS[@]}"; do
  if git grep -qi -- "$t"; then
    echo "Privacy violation: a denylisted term was found in tracked files."
    exit 1
  fi
done
echo "Privacy check passed."
