# Baseline Report — Pre-Change State

Date: 2026-09-02
Scope: Snapshot of `DevSecOps-CI-CD-Project` exactly as received, before any repair/implementation work in this
engagement. This file records what was verified to work, what was broken, and what was missing, with commands
and raw output. It is the reference point for everything in `docs/GAP_ANALYSIS.md` and the change log in
`CONTEXT.md`.

Environment used to produce this baseline: a Linux cloud workspace with Python 3.11.15, pip 24.0, Docker **CLI**
present but **no Docker daemon reachable** (`/var/run/docker.sock` does not exist in this sandbox), no `helm`,
`kubectl`, `opa`, `trivy`, `gitleaks`, `tfsec`/`checkov` binaries preinstalled. Where a tool could not run, that is
recorded explicitly below rather than assumed — see "Not Verified" at the end.

## 1. Build Status

| Step | Result | Notes |
|---|---|---|
| `pip install -r app/requirements.txt` | ❌ **FAILED initially** | `pytest-cov==4.1.1` does not exist on PyPI (closest real release is `4.1.0`). This is a hard pin error — a fresh clone cannot install dependencies at all until fixed. **Fixed** in this engagement (see CONTEXT.md Change #1). |
| `python3 -m py_compile` on `app/app.py`, `ai-agents/*.py`, `app/tests/*.py` | ✅ PASS | No syntax errors in any Python file. |
| `docker build -t devsecops-app ./app` (via `app/Dockerfile`) | ⚠️ NOT VERIFIED | No Docker daemon available in this sandbox. Dockerfile was reviewed manually (see Section 4) instead of built. |

## 2. Test Status

Command: `cd app && python3 -m pytest tests/ -v`

```
tests/test_app.py::test_home PASSED
tests/test_app.py::test_health PASSED
tests/test_app.py::test_get_users PASSED
tests/test_app.py::test_create_user PASSED
tests/test_app.py::test_create_user_missing_fields PASSED
tests/test_app.py::test_search FAILED
assert 404 == 200 (route /search does not exist in app.py)

1 failed, 5 passed
```

**Finding:** `app/tests/test_app.py` tests a `/search` endpoint that is not implemented in `app/app.py`. The test
suite was written ahead of (or was left behind by) the application code — a genuine broken/incomplete feature,
not a flaky test. This is fixed in this engagement by implementing `/search` securely (parameterized query, input
validation) rather than deleting the test.

## 3. Static Security Scan Status (baseline, before fixes)

**Bandit** (`bandit -r app -f json -o reports/bandit-report.json --severity-level medium`):

| ID | Finding | File | Severity |
|---|---|---|---|
| B104 | Possible binding to all interfaces (`0.0.0.0`) | `app/app.py` (`app.run(host='0.0.0.0', ...)`) | MEDIUM |
| B108 | Probable insecure usage of temp file/directory (`/tmp/users.db` default) | `app/app.py` | MEDIUM |

Both are expected/acceptable for a containerized service (binding `0.0.0.0` inside a container is normal; the
`/tmp` DB path is a demo default, not a production data store) but both are documented and the `/tmp` default is
tightened in this engagement (configurable path, non-world-writable permissions) — see `docs/SECURITY.md`.

**Semgrep** (`semgrep --config security/semgrep-rules.yaml app --json`): **0 findings**. The custom rule set
(hardcoded passwords, string-concatenated SQL, `eval()`, shell injection, Flask debug mode) found nothing — the
existing `app.py` already used parameterized SQLite queries (`?` placeholders) and no `eval`/`debug=True`. This
is a genuine strength of the existing code that was preserved.

**Secret scan** (manual regex sweep for API keys / passwords / tokens / private keys across `*.py`, `*.yml`,
`*.yaml`, `*.json`, `*.sh`, `*.tf`, `*.md`): no hardcoded credentials found. One weak default was found and is
addressed: `docker-compose.yml` sets `GF_SECURITY_ADMIN_PASSWORD=admin123` for local Grafana — a well-known
default that must be overridden for any shared/non-laptop use. Documented in `docs/SECURITY.md` and moved to an
environment variable with a placeholder in `.env.example`.

**IaC lint** (`yamllint` on `kubernetes/`, `monitoring/`, `docker-compose.yml`, and the Helm chart's plain
non-templated files): 0 issues. (Linting the raw Helm `templates/*.yaml` files directly produces false-positive
"too many spaces inside braces" errors because yamllint parses Go template `{{ }}` syntax as YAML flow mappings —
this is expected for unrendered Helm templates and is not a real defect.)

## 4. Manual Review Findings (no tool required)

- `app/Dockerfile`: already uses a slim base image, multi-stage-style dependency caching, a non-root user
  (`appuser`, UID 10001 matching the Kubernetes `runAsUser`), and `gunicorn` instead of the Flask dev server.
  No `HEALTHCHECK` instruction present (Kubernetes probes cover this at the orchestration layer, but a
  container-level `HEALTHCHECK` is still missing for plain `docker run` use — flagged as a gap).
- `Jenkinsfile` stages (`Checkout → SAST → Dependency Scan → AI Code Review & MLflow Logging → Container Scan →
  OPA Gate → Deploy → DAST`) do **not** call three of the four AI/LLM scripts that exist in `ai-agents/`:
  `hf_code_analyzer.py` (HuggingFace vulnerability classifier) and `code_indexer.py` (LlamaIndex documentation
  generator) are never invoked by the pipeline, and `mlflow_logger.py` — which logs all three — is only run
  once, immediately after `code_reviewer.py`, before the other two reports exist to log. There is also no
  unit-test stage, no lint stage, no SonarQube stage (despite `sonarqube/sonar-project.properties` and a
  `sonarqube` service in `docker-compose.yml` existing), and no secret-scanning stage anywhere in the pipeline.
- `ai-agents/code_reviewer.py`, `ai-agents/hf_code_analyzer.py`, and `ai-agents/code_indexer.py` all call
  `os.system("pip install ... -q")` at runtime with **unpinned** package versions if the import fails. This is a
  software-supply-chain weakness (non-reproducible builds, no version pinning, arbitrary code executed at
  pipeline runtime from whatever is latest on PyPI at that moment).
- No `chaos/` directory exists despite `README.md` referencing it as a placeholder for LitmusChaos experiments —
  the README overstates what is in the repository.
- `monitoring/loki-config.yaml` configures Loki to receive logs, and `docker-compose.yml` runs a Loki container,
  but **no log-shipping agent (e.g. Promtail) is configured anywhere** — nothing actually ships container logs to
  Loki. The "Loki collects logs" claim in `README.md` was not true as shipped.
- `app/app.py` has no authentication/authorization on any route (including `POST /users`, which writes to the
  database) and no rate limiting, input length limits, or structured logging.
- `terraform/` provisions security/governance primitives (KMS, CloudTrail, GuardDuty, Security Hub, Secrets
  Manager, an IAM role) but does not provision the Kubernetes cluster, VPC, or networking that the
  `kubernetes/`/`helm/` manifests assume — it targets an externally-provisioned cluster. This is a legitimate
  scope boundary, not a bug, but is under-documented.

## 5. Not Verified in This Environment (external dependency)

The following require infrastructure this sandbox does not have (a running Docker daemon, a Kubernetes cluster,
network egress to Jenkins/SonarQube/Snyk services, GPU/CPU budget to download multi-hundred-MB Hugging Face
models). They are reviewed by static/manual inspection instead of executed, and are called out explicitly rather
than claimed as passing:

- `docker build` of `app/Dockerfile` and any Trivy container scan.
- `helm template` / `helm install` (no `helm` binary in this sandbox).
- `kubectl apply` against a live cluster.
- OWASP ZAP dynamic scan (`security/zap-runner.sh`) — requires a running target and Docker.
- Live OPA evaluation (`security/test_policy.sh`) — requires `opa` binary or Docker; the Rego policy logic itself
  was reviewed by hand against both example manifests and is logically correct (see `docs/SECURITY.md`).
- Live Hugging Face Transformers inference (`ai-agents/hf_code_analyzer.py` downloading
  `distilbert-base-uncased-finetuned-sst-2-english`) and live Ollama/LangChain calls in `code_reviewer.py` — both
  scripts' documented fallback paths (used when the model/service is unavailable) were exercised instead, and
  both produced valid fallback reports as designed.
- Terraform `plan`/`apply` — requires AWS credentials that must never be entered into this session.

None of these gaps are hidden or assumed fixed; they are tracked in `docs/GAP_ANALYSIS.md` and their status is
carried into `docs/FINAL_AUDIT.md` as "requires external environment," not "complete."
