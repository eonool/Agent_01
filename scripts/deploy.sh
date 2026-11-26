#!/usr/bin/env bash
# Deploy Agent_01 to Cloud Run with the ADK CLI.
# Usage: GOOGLE_CLOUD_PROJECT=<project> GOOGLE_CLOUD_LOCATION=us-central1 scripts/deploy.sh
set -euo pipefail
: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
: "${GOOGLE_CLOUD_LOCATION:=us-central1}"
adk deploy cloud_run \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$GOOGLE_CLOUD_LOCATION" \
  --service_name agent-01 \
  --with_ui \
  agent_01
