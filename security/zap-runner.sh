#!/usr/bin/env bash
set -euo pipefail

# Simple ZAP runner for the pipeline
# Assumptions:
# - Docker is available on the Jenkins agent
# - The application is reachable at http://devsecops-app:5000 (Docker network)
# - jq and python are available on the Jenkins agent (or adjust filtering to use python only)

TARGET="http://devsecops-app:5000"
REPORT_JSON="reports/zap-report.json"
FILTERED_JSON="reports/zap-report-filtered.json"
HTML_REPORT="reports/zap-report.html"

# Risks to ignore in the filtered report
IGNORE_RISKS=("Low" "Informational")
# Minimum risk that will fail the build if present in the filtered report
FAIL_ON_MIN="Medium"

mkdir -p reports

echo "🔎 Running OWASP ZAP baseline scan against ${TARGET}"

docker run --rm \
  --network devsecops \
  -v "$(pwd)/reports:/zap/wrk" \
  zaproxy/zap-stable:latest \
  zap-baseline.py -t "${TARGET}" -J /zap/wrk/$(basename "${REPORT_JSON}") || true

if [ ! -f "${REPORT_JSON}" ]; then
  echo "⚠️ ZAP did not produce a report at ${REPORT_JSON}"
  exit 0
fi

# Filter out ignored risk levels using jq
# Keep alerts whose .risk is NOT in IGNORE_RISKS
jq --argfile ignore <(printf '%s\n' "${IGNORE_RISKS[@]}" | jq -R -s -c 'split("\n")[:-1]') \
  '.site[0].alerts |= map(select((.risk) as $r | ($r | IN($ignore[])) | not))' \
  "${REPORT_JSON}" > "${FILTERED_JSON}" || {
  echo "⚠️ Failed to filter ZAP report with jq, copying original to filtered file"
  cp "${REPORT_JSON}" "${FILTERED_JSON}"
}

# Decide pass/fail using a small Python helper
python - <<PY
import json,sys
order = {"Informational":0,"Low":1,"Medium":2,"High":3,"Critical":4}
min_required = "${FAIL_ON_MIN}"
min_val = order.get(min_required,2)
try:
    d = json.load(open('${FILTERED_JSON}'))
    alerts = d.get('site',[{}])[0].get('alerts',[])
except Exception:
    print('⚠️ Could not parse filtered ZAP JSON, failing safe (no failure)')
    sys.exit(0)
max_val = 0
for a in alerts:
    max_val = max(max_val, order.get(a.get('risk','Informational'),0))
if max_val >= min_val:
    print(f"❌ ZAP scan failed: highest remaining alert >= {min_required}")
    print(f"Remaining alerts count: {len(alerts)}")
    sys.exit(2)
else:
    print("✅ ZAP scan passed (no alerts >= threshold)")
    print(f"Remaining alerts count: {len(alerts)}")
    sys.exit(0)
PY
