#!/usr/bin/env bash
set -euo pipefail

# Test harness for OPA policy.security/policy.rego
# Verifies that the policy rejects the bad manifest and accepts the good manifest.

POLICY="security/policy.rego"
GOOD_MANIFEST="security/examples/good-deployment.yaml"
BAD_MANIFEST="security/examples/bad-deployment.yaml"

OPA_CMD=""

# prefer local opa binary, fallback to docker
if command -v opa >/dev/null 2>&1; then
  OPA_CMD=(opa eval --input)
  OPA_RUNNER() { opa eval -i "$1" -d "$2" 'data.kubernetes.admission.deny' --format json; }
else
  if command -v docker >/dev/null 2>&1; then
    OPA_CMD=(docker run --rm -v "$(pwd)":/workspace openpolicyagent/opa:0.61.1 eval -i /workspace/"$1" -d /workspace/"$2" 'data.kubernetes.admission.deny' --format json)
    OPA_RUNNER() { docker run --rm -v "$(pwd)":/workspace openpolicyagent/opa:0.61.1 eval -i "/workspace/$1" -d "/workspace/$2" 'data.kubernetes.admission.deny' --format json; }
  else
    echo "❌ opa binary or docker is required to run this test harness"
    exit 2
  fi
fi

run_check() {
  local manifest="$1"
  local expected="$2" # "allow" or "deny"

  echo "\n🔎 Testing manifest: ${manifest} (expect: ${expected})"

  if command -v opa >/dev/null 2>&1; then
    out=$(opa eval -i "$manifest" -d "$POLICY" 'data.kubernetes.admission.deny' --format json)
  else
    out=$(docker run --rm -v "$(pwd)":/workspace openpolicyagent/opa:0.61.1 eval -i "/workspace/$manifest" -d "/workspace/$POLICY" 'data.kubernetes.admission.deny' --format json)
  fi

  # parse JSON output to see if there are deny results
  denies=$(echo "$out" | python -c "import json,sys; d=json.load(sys.stdin); r=d.get('result', []); print(len(r))")

  if [ "$expected" = "allow" ]; then
    if [ "$denies" -ne 0 ]; then
      echo "❌ Policy DENIED manifest but expected allow: ${manifest}"
      echo "Policy output:"; echo "$out"
      return 1
    else
      echo "✅ Policy allowed (as expected): ${manifest}"
      return 0
    fi
  else
    if [ "$denies" -eq 0 ]; then
      echo "❌ Policy did NOT deny manifest but expected deny: ${manifest}"
      echo "Policy output:"; echo "$out"
      return 1
    else
      echo "✅ Policy denied (as expected): ${manifest}"
      echo "Deny count: ${denies}"
      return 0
    fi
  fi
}

failures=0

if ! run_check "$GOOD_MANIFEST" "allow"; then failures=$((failures+1)); fi
if ! run_check "$BAD_MANIFEST" "deny"; then failures=$((failures+1)); fi

if [ "$failures" -eq 0 ]; then
  echo "\n🎉 All policy tests passed"
  exit 0
else
  echo "\n❌ Policy tests failed: ${failures} failures"
  exit 1
fi
