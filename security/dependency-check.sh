#!/usr/bin/env bash
set -euo pipefail

# Run OWASP Dependency-Check against Python requirements and produce an HTML report
# Outputs: reports/dependency-check-report.html

REQ_FILE="app/requirements.txt"
OUT_DIR="reports"
OUT_HTML="${OUT_DIR}/dependency-check-report.html"
PROJECT_NAME="devsecops-python-deps"

mkdir -p "${OUT_DIR}"

if [ ! -f "${REQ_FILE}" ]; then
  echo "⚠️ Requirements file not found: ${REQ_FILE}"
  exit 0
fi

# Prefer Docker image for dependency-check to avoid requiring Java locally
if command -v docker >/dev/null 2>&1; then
  echo "🔎 Running OWASP Dependency-Check via Docker..."
  docker run --rm -v "$(pwd)":/src -u "$(id -u):$(id -g)" owasp/dependency-check:latest \
    --project "${PROJECT_NAME}" \
    --scan "/src/${REQ_FILE}" \
    --format HTML \
    --out "/src/${OUT_DIR}" || true

  if [ -f "${OUT_HTML}" ]; then
    echo "✅ Dependency-Check report generated: ${OUT_HTML}"
    exit 0
  else
    echo "⚠️ Dependency-Check did not produce HTML report at expected path: ${OUT_HTML}"
  fi
fi

# Fallback: try local dependency-check CLI if installed
if command -v dependency-check.sh >/dev/null 2>&1; then
  echo "🔎 Running local OWASP Dependency-Check CLI..."
  dependency-check.sh --project "${PROJECT_NAME}" --scan "${REQ_FILE}" --format HTML --out "${OUT_DIR}" || true
  if [ -f "${OUT_HTML}" ]; then
    echo "✅ Dependency-Check report generated: ${OUT_HTML}"
    exit 0
  else
    echo "⚠️ Local dependency-check did not produce HTML report at ${OUT_HTML}"
  fi
fi

echo "❌ Dependency-Check not available. Install Docker or the dependency-check CLI to generate the report."
exit 2
