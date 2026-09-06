# CONTEXT — Persistent Project Memory

Read this file first in any future session before touching this repository. It is the single source of truth
for what this project is, what state it's in, and what to do next.

## Project Context

**Project Name**: DevSecOps-CI-CD-Project (AI-Augmented DevSecOps Pipeline)

**Project Purpose**: Exam project for Al-Nafi International College's EduQual Level 6 Diploma in AIOPS —
"Implementing AI-Augmented DevSecOps Pipeline with LLMOps, Security Intelligence, and Regulatory Compliance"
(see `Ayesha exam req.pdf` in the parent folder for the original requirements, and `ayesha ppt.pdf` for the
student's oral-presentation deck). A working, security-first CI/CD pipeline for a small Flask app, with three
real AI/LLM integrations (LangChain+Ollama code review, Hugging Face vulnerability triage, LlamaIndex docs) each
tracked via MLflow.

**Current Status**: **MOSTLY COMPLETE**. Everything that could be executed and verified in this engagement's
sandbox (no Docker daemon, no Kubernetes cluster, no live Jenkins agent, no AWS credentials, no live Ollama
server, no Hugging Face Hub network access) was executed and verified. Everything that needed one of those
external dependencies was reviewed by hand/static tooling and is explicitly labeled "requires external
environment" rather than claimed as tested. See `docs/FINAL_AUDIT.md` for the full, itemized breakdown.

## Original Requirements
See `docs/GAP_ANALYSIS.md` "Required Features" for the full extraction from `Ayesha exam req.pdf`. In short:
Jenkins/GitLab CI/CD with security at every stage; Hugging Face/LangChain/LlamaIndex LLM integration; MLflow/
Kubeflow model management; Trivy/Semgrep-or-Bandit/OWASP Dependency-Check security scanning; SonarQube + OWASP
ZAP; Prometheus + Grafana; network/data/system architecture diagrams; a reproducible, well-structured GitHub
repository; ISO/IEC 42001, NIST AI RMF, and GDPR alignment.

## Technology Stack
Python 3.11 / Flask / gunicorn / SQLite · Jenkins (Groovy) · Docker · Kubernetes + Helm 3 · Terraform (AWS,
~5.0 provider) · LangChain + langchain-community + Ollama · Hugging Face Transformers + llama-index-embeddings-
huggingface · LlamaIndex + Ollama · MLflow · Bandit, Semgrep, Snyk, OWASP Dependency-Check, Trivy, gitleaks,
checkov, OPA/Rego, OWASP ZAP · Prometheus, Grafana, Loki, Promtail.

## Repository Structure
```
.
├── app/                    # Flask application + pytest tests
├── ai-agents/              # 4 AI/LLM CI-stage scripts + their own pinned requirements.txt
├── security/               # scanner configs, OPA policy + test harness, security_gate.py (new)
├── kubernetes/             # plain manifests (namespace.yaml is new)
├── helm/devsecops-app/     # equivalent Helm chart
├── terraform/              # AWS governance IaC (variables.tf is new)
├── monitoring/             # Prometheus, Loki, Grafana dashboard, promtail-config.yaml (new)
├── docker-compose.yml      # local toolchain incl. the app itself, Loki, Promtail (all new additions)
├── Jenkinsfile             # rebuilt stage list (see Change Log)
├── .env.example            # new — documents every env var used anywhere in the repo
├── README.md               # corrected to match actual repo contents
├── CONTEXT.md              # this file
└── docs/
    ├── BASELINE.md          # pre-change state, what was tested and how
    ├── GAP_ANALYSIS.md      # requirements vs. implementation, prioritized
    ├── IMPLEMENTATION_PLAN.md
    ├── PRD.md
    ├── TRD.md
    ├── SECURITY.md          # includes the required LLM Security + Threat Model sections
    ├── FLOW.md              # Mermaid diagrams: user/app/LLM/CI-CD/deployment/incident flow
    ├── ARCHITECTURE.md      # Mermaid diagrams: high-level, component
    └── FINAL_AUDIT.md       # what was verified, what wasn't, final status
```

## Architecture
See `docs/ARCHITECTURE.md` for diagrams. In one sentence: a Flask app, containerized and deployed to Kubernetes
behind an Nginx Ingress, built/tested/scanned/deployed by a Jenkins pipeline that also runs three independent
AI/LLM helper scripts (code review, vulnerability triage, doc generation) tracked via MLflow, secured by
SAST/SCA/secret/container/IaC scanning plus an OPA admission policy and NetworkPolicy zero-trust rules, and
observed via Prometheus/Grafana/Loki+Promtail. Terraform separately manages AWS-account governance around an
assumed pre-existing cluster.

## Components
See "Repository Structure" above and `docs/TRD.md` Section 2 for detail on each.

## LLM / Hugging Face
Three integrations (LangChain+Ollama, Hugging Face Transformers, LlamaIndex+Ollama+HF embeddings), each with a
working fallback, all logged to MLflow. **Preserved and hardened, not replaced**, per the engagement's explicit
instruction. Known, documented limitation: `hf_code_analyzer.py`'s classifier
(`distilbert-base-uncased-finetuned-sst-2-english`) is a sentiment model repurposed as a security-priority
proxy — a semantic mismatch, called out honestly in `docs/SECURITY.md` rather than hidden or silently "fixed"
by swapping the model without being asked to.

## DevSecOps Pipeline
Rebuilt `Jenkinsfile` stage order: Checkout → Install Dependencies → Lint → Unit Tests → SAST → SonarQube →
Secret Scan → SCA → AI Review/Analysis/Docs → MLflow Logging → Container Build → Container Scan → IaC Scan →
OPA Gate → Security Gate → Deploy → DAST → Post-Deployment Verification. See `docs/TRD.md` Section 11 for the
rationale on every addition.

## Security Controls
See `docs/SECURITY.md` in full — Secure SDLC mapping, SAST/SCA/secret/container/IaC/DAST tooling, auth,
data security, LLM security (dedicated section), and a threat model table.

## Infrastructure
Kubernetes (plain manifests + Helm, hardened securityContext, dedicated `devsecops` namespace, zero-trust
NetworkPolicy) + Terraform (AWS governance: KMS, CloudTrail, GuardDuty, Security Hub, Secrets Manager, IAM
role — cluster itself assumed pre-existing, not provisioned here).

## Deployment
`kubectl apply -f kubernetes/` (apply `namespace.yaml` first) or `helm install devsecops-app
./helm/devsecops-app --namespace devsecops --create-namespace`. See README.md "Setup & Execution Guide".

## Testing
`app/tests/test_app.py`: 12 pytest cases, all passing, 97% line coverage of `app.py` (verified in this sandbox
— see `docs/BASELINE.md` and `docs/FINAL_AUDIT.md` for the exact commands and output).

## Completed Work
See "Change Log" below for the itemized, dated list. Summary: fixed a broken dependency pin that blocked all
installs; implemented the missing `/search` endpoint; added authentication, validation, rate limiting, and
structured logging to the Flask app; removed unpinned runtime `pip install` calls from all four AI scripts and
pinned their dependencies; fixed a real bug where `mlflow_logger.py` could hang indefinitely against an
unreachable MLflow server; synced the Jenkinsfile to actually run every stage the repo's tooling supports
(previously 2 of 3 AI scripts and SonarQube were configured but never invoked); added secret scanning
(gitleaks), IaC scanning (checkov) and an aggregated Security Gate stage; hardened Terraform (S3 encryption/
versioning/public-access-block/lifecycle, CloudTrail multi-region/log validation/CloudWatch integration, an
explicit KMS key policy) and Kubernetes (dedicated namespace, full container securityContext hardening) —
verified with checkov (Terraform 48/54, Kubernetes 93/94, remaining gaps documented); added Loki+Promtail so the
"logs are collected" claim in the README is actually true; removed a hardcoded Grafana default password; wrote
the complete documentation set required by this engagement.

## Current Work
None in progress — this engagement's scope is complete as of the state described in `docs/FINAL_AUDIT.md`.

## Remaining Work
See `docs/PRD.md` Section 21 "Future Improvements" and the accepted-scope gaps listed in `docs/SECURITY.md`
Sections 6 and 8. Highest-value next steps, in rough priority order:
1. Verify the full pipeline (Jenkinsfile, Docker build, Helm template render, live ZAP/OPA runs) on a real
   machine with Docker/Kubernetes/Jenkins available — this sandbox could not run any of those.
2. Replace the sentiment-model-as-security-classifier in `hf_code_analyzer.py` with a purpose-built model.
3. Pin the Kubernetes/Helm container image to a real digest once CI has actually published one.
4. Provision the Kubernetes cluster itself via Terraform (currently assumed pre-existing).
5. If real user data is ever handled, add a data-retention/deletion job for the `users` table and move off
   SQLite/`emptyDir` to a real database + PersistentVolumeClaim.

## Known Issues
- `Jenkinsfile`, `security/zap-runner.sh`, `security/test_policy.sh`'s live (non-fallback) OPA path, and
  `docker-compose.yml`'s full stack were reviewed but not executed end-to-end (no Docker daemon in this
  sandbox). Treat as "reviewed, not integration-tested" until run on a real machine.
- Terraform HCL was reviewed and scanned with `checkov` (which does its own parsing) but `terraform validate`
  itself could not run (no network access to `releases.hashicorp.com` in this sandbox to fetch the `terraform`
  binary). Run `terraform validate` yourself before `terraform apply`.
- `helm template` could not run (no `helm` binary in this sandbox) — the chart was reviewed by hand for
  Go-template correctness against the existing working templates' style.

## Known Limitations
See `docs/PRD.md` Sections 13–18 and `docs/SECURITY.md` Sections 6, 8, 10, 11 for the full, honest list —
SQLite/emptyDir is not HA storage; the rate limiter doesn't coordinate across replicas; no RBAC manifests exist;
TLS-version/OAuth2/JWT/mTLS claims from the presentation are only partially implemented (Ingress TLS
termination yes; the rest requires infrastructure — a service mesh, an IdP — this repo doesn't provision).

## Important Decisions
- **Did not replace the Hugging Face sentiment model** used for vulnerability triage, per the explicit
  instruction to preserve working LLM functionality — documented the mismatch instead of silently "fixing" it.
- **Did not fabricate a container image digest, a specific HF model commit hash, or a `terraform validate`
  pass** — where verification required something this sandbox didn't have, that is stated plainly rather than
  guessed at.
- **Kept the pipeline's non-blocking (`|| true`) security-scan philosophy** (opt-in enforcement via
  `ENFORCE_SECURITY`) rather than silently making scans blocking by default — this was the existing repo's
  explicit, documented design choice, not an oversight to "fix" unilaterally. Centralized the enforcement
  decision into one new `Security Gate` stage instead of leaving it scattered.
- **Added a dedicated `devsecops` Kubernetes namespace** rather than leaving manifests in `default` — a
  clear, low-risk, checkov-flagged fix.
- **Used SIGALRM for the MLflow connect-timeout fix** (Unix-only) since Jenkins/Linux CI is this repo's only
  target environment — documented that tradeoff in the code comment.

## Files Changed
See `git diff --stat` in the working copy used for this engagement, or the itemized Change Log below. Every
file touched has an inline comment explaining what changed and why, at the point of the change — not just in
this document.

## Commands Used
```
pip install -r app/requirements.txt          # (fixed: pytest-cov==4.1.1 -> 4.1.0)
pip install -r ai-agents/requirements.txt    # new file
cd app && python3 -m pytest tests/ -v --cov=. --cov-report=term-missing
bandit -r app -f json -o reports/bandit-report.json --severity-level medium
semgrep --config security/semgrep-rules.yaml app --json --output reports/semgrep-report.json
flake8 app --max-line-length=120
checkov -d terraform --output json --quiet
checkov -d kubernetes --framework kubernetes --output json --quiet
python3 security/security_gate.py --enforce=false   # and --enforce=true
python3 ai-agents/code_reviewer.py / hf_code_analyzer.py / code_indexer.py / mlflow_logger.py
```

## Test Results
12/12 pytest cases passing, 97% line coverage of `app.py`. Bandit: 2 medium findings, both documented/accepted.
Semgrep: 0 findings. flake8: 0 findings. checkov: Terraform 48/54 (6 documented accepted gaps), Kubernetes
93/94 (1 documented accepted gap). All four AI scripts run to completion via their fallback paths without
raising. See `docs/BASELINE.md` and `docs/FINAL_AUDIT.md` for full detail.

## Security Results
See "Test Results" above and `docs/SECURITY.md` in full. No hardcoded secrets found (verified by regex sweep
before and after all changes).

## Configuration Requirements / Environment Variables
See `.env.example` for the complete, documented list (app: `APP_DB`, `APP_API_KEY`, `LOG_LEVEL`; AI agents:
`MLFLOW_HOST`, `MLFLOW_CONNECT_TIMEOUT_SECONDS`, `BUILD_NUMBER`, `HF_MODEL_REVISION`; compose:
`GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`; CI tools: `SNYK_TOKEN`, `SONAR_HOST_URL`, `SONAR_TOKEN`). No
real secrets are recorded anywhere in this repository or in this file.

## How to Run Locally
```bash
cp .env.example .env   # then fill in real values
docker compose up -d   # brings up the app + full local toolchain (needs a Docker daemon)
```

## How to Build
```bash
docker build -t devsecops-app:local -f app/Dockerfile .
```

## How to Test
```bash
cd app && python3 -m pytest tests/ -v --cov=. --cov-report=term-missing
bandit -r app -f json -o reports/bandit-report.json --severity-level medium
semgrep --config security/semgrep-rules.yaml app --json --output reports/semgrep-report.json
```

## How to Deploy
```bash
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/
# or
helm install devsecops-app ./helm/devsecops-app --namespace devsecops --create-namespace
```

## How to Continue Development
1. Read this file, then `docs/GAP_ANALYSIS.md` and `docs/FINAL_AUDIT.md` for what's done vs. outstanding.
2. Pick an item from "Remaining Work" above.
3. Make the change, run the relevant command from "How to Test," and update this file's Change Log below
   *immediately* — not at the end of a longer session.
4. Keep `docs/*.md` synchronized with whatever you changed — never leave a doc claiming something the code no
   longer does (or doesn't yet do).

---

## Change Log

### 2026-09-02 — Change #1: Fix broken dependency pin blocking all installs
- **Change**: `app/requirements.txt`: `pytest-cov==4.1.1` → `pytest-cov==4.1.0` (the `4.1.1` release does not
  exist on PyPI).
- **Reason**: `pip install -r app/requirements.txt` failed outright on a clean environment — nobody could build
  this project as shipped.
- **Files**: `app/requirements.txt`
- **Tests**: `pip install -r app/requirements.txt` — now succeeds.
- **Result**: Fixed.
- **Remaining Issues**: None.

### 2026-09-02 — Change #2: Implement missing `/search` endpoint + app security hardening
- **Change**: Added `/search` (parameterized `LIKE` query), API-key auth on `POST /users`, input validation
  (length + regex), a simple in-process rate limiter on `/users` (POST) and `/search`, and structured
  request logging.
- **Reason**: `app/tests/test_app.py::test_search` tested a route that didn't exist (404); the app had no
  authentication, validation, rate limiting, or logging at all.
- **Files**: `app/app.py`, `app/tests/test_app.py`
- **Tests**: `pytest tests/ -v --cov=. --cov-report=term-missing` — 12/12 passed, 97% coverage.
- **Result**: Fixed and covered by new tests.
- **Remaining Issues**: Rate limiter doesn't coordinate across multiple workers/replicas — documented.

### 2026-09-02 — Change #3: Container HEALTHCHECK
- **Change**: Added `HEALTHCHECK` to `app/Dockerfile` hitting `/health`.
- **Reason**: Kubernetes probes already existed but plain `docker run` had no health signal.
- **Files**: `app/Dockerfile`
- **Tests**: Manual review (no Docker daemon in sandbox to build/run — see Known Issues).
- **Result**: Implemented, not integration-tested in this sandbox.
- **Remaining Issues**: Verify with `docker build && docker inspect --format='{{.State.Health.Status}}'` on a
  machine with Docker.

### 2026-09-02 — Change #4: Harden AI/LLM agent scripts
- **Change**: Removed runtime `os.system("pip install ...")` from `code_indexer.py`, `hf_code_analyzer.py`,
  `mlflow_logger.py`; added `ai-agents/requirements.txt` with pinned versions; added `HF_MODEL_REVISION` pinning
  support in `hf_code_analyzer.py`; added a 20,000-char prompt-size guard in `code_reviewer.py`; fixed
  `code_reviewer.py`'s static fallback text (was describing SQL-injection/no-validation issues already fixed
  by Change #2 — a documentation-accuracy bug); fixed a real bug in `mlflow_logger.py` where an unreachable
  MLflow server could hang the script indefinitely (added a `SIGALRM`-based 10s hard timeout).
- **Reason**: Unpinned runtime installs are a supply-chain risk; a stale fallback report actively misinforms;
  an indefinite hang in a Jenkins stage is a real reliability bug.
- **Files**: `ai-agents/code_indexer.py`, `ai-agents/hf_code_analyzer.py`, `ai-agents/code_reviewer.py`,
  `ai-agents/mlflow_logger.py`, `ai-agents/requirements.txt` (new)
- **Tests**: Ran all four scripts directly in the sandbox (no Ollama/HF/MLflow network available) — each hit
  its fallback path and produced a valid report/doc/skip message with no unhandled exception; the
  `mlflow_logger.py` timeout fix was specifically verified (previously hung past a 2-minute test timeout,
  now completes in seconds).
- **Result**: Fixed and verified (fallback paths). Live paths (real Ollama/HF Hub/MLflow) not exercised in this
  sandbox — see Known Issues.
- **Remaining Issues**: `HF_MODEL_REVISION` has no default real commit hash pinned (no Hub network access to
  fetch one) — defaults to `main` with an explicit warning instead.

### 2026-09-02 — Change #5: Sync Jenkinsfile with actual repository contents
- **Change**: Rebuilt the stage list to add Install Dependencies, Lint, Unit Tests, SonarQube Analysis, Secret
  Scan (gitleaks), the two missing AI scripts (`hf_code_analyzer.py`, `code_indexer.py`), IaC Scan (checkov), a
  new aggregated Security Gate stage, and Post-Deployment Verification; moved MLflow Logging to after all three
  AI reports exist.
- **Reason**: The pipeline as shipped never invoked 2 of 3 AI scripts, never ran SonarQube despite it being
  provisioned, had no test/lint stage, and had no secret/IaC scanning at all.
- **Files**: `Jenkinsfile`, `security/security_gate.py` (new)
- **Tests**: Reviewed line-by-line; verified brace/paren balance; ran the underlying scripts each stage calls
  directly in this sandbox as a proxy for stage correctness (pytest, bandit, semgrep, the AI scripts,
  `security_gate.py` in both advisory and enforce mode against real generated reports).
- **Result**: Implemented; full Jenkins execution is **[external]** — requires a real Jenkins agent.
- **Remaining Issues**: None known; flag any Groovy syntax issue found on first real Jenkins run back here.

### 2026-09-02 — Change #6: Secret scanning + secrets hygiene
- **Change**: Added `security/gitleaks.toml`; added `.env.example` documenting every env var in the repo;
  removed the hardcoded Grafana `admin123` default from `docker-compose.yml` (now a required env var with no
  default).
- **Reason**: No secret-scanning gate existed; a well-known default credential was hardcoded.
- **Files**: `security/gitleaks.toml` (new), `.env.example` (new), `docker-compose.yml`
- **Tests**: Manual regex secret-sweep before/after — no real secrets found either time; confirmed `admin123`
  only remains in historical documentation/comments (docs/BASELINE.md, docs/GAP_ANALYSIS.md), not live config.
- **Result**: Fixed.
- **Remaining Issues**: None.

### 2026-09-02 — Change #7: Observability — Loki actually receives logs
- **Change**: Added `loki` and `promtail` services to `docker-compose.yml`; added
  `monitoring/promtail-config.yaml`; added a `devsecops-app` service to `docker-compose.yml` (it was entirely
  absent, so Prometheus's and ZAP's configured targets never existed in the compose stack).
- **Reason**: Loki was configured and Grafana had a Loki-backed panel, but nothing shipped any logs to Loki,
  and no service Prometheus/ZAP could actually scrape/target existed in `docker-compose.yml`.
- **Files**: `docker-compose.yml`, `monitoring/promtail-config.yaml` (new)
- **Tests**: YAML-validated with PyYAML; Promtail Docker service-discovery config reviewed against the Loki
  push API contract. Full end-to-end log flow is **[external]** (needs a Docker daemon).
- **Result**: Implemented; not integration-tested in this sandbox.
- **Remaining Issues**: Run `docker compose up -d` on a real machine and confirm log lines appear in Grafana's
  "Application Security Logs" panel.

### 2026-09-02 — Change #8: Terraform hardening
- **Change**: Added `terraform/variables.tf` (region/env/project as variables, same defaults); added S3 public
  access block, versioning, KMS server-side encryption, a lifecycle policy, and an explicit bucket policy for
  the CloudTrail log bucket; made CloudTrail multi-region with log-file validation and CloudWatch Logs
  integration (new `aws_cloudwatch_log_group` + IAM role); added an explicit KMS key policy; changed the
  Secrets Manager `recovery_window_in_days` from `0` (immediate, unrecoverable delete) to `7`.
- **Reason**: `checkov` found 14 failed checks against the original `main.tf`; several (unencrypted/
  unversioned/publicly-accessible-by-default S3 bucket, no CloudTrail log validation, immediate secret
  deletion) are genuine security weaknesses, not just linter noise.
- **Files**: `terraform/main.tf`, `terraform/variables.tf` (new), `terraform/provider.tf`, `terraform/outputs.tf`
- **Tests**: `checkov -d terraform` — went from 17 passed/14 failed to 48 passed/6 failed. The 6 remaining are
  documented accepted-scope gaps (see `docs/SECURITY.md` Section 8) requiring infrastructure disproportionate
  to this project's scope (an SNS topic + subscriber, a second logging bucket, a rotation Lambda, an AWS
  Organizations context). `terraform validate` itself could not run — no network access to download the
  `terraform` binary in this sandbox.
- **Result**: Fixed (48/54); remainder documented, not hidden.
- **Remaining Issues**: Run `terraform validate` and `terraform plan` on a machine with the `terraform` CLI and
  appropriate AWS credentials before ever running `apply`.

### 2026-09-02 — Change #9: Kubernetes/Helm hardening
- **Change**: Added `kubernetes/namespace.yaml` (dedicated `devsecops` namespace) and moved all manifests to it
  from `default`; added container-level `securityContext` (`allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true` with explicit `/data`+`/tmp` `emptyDir` volumes, `capabilities: drop: [ALL]`),
  pod-level `seccompProfile: RuntimeDefault`, `automountServiceAccountToken: false`, `imagePullPolicy: Always`;
  mirrored all of this into the Helm chart (`values.yaml` + `templates/deployment.yaml`).
- **Reason**: `checkov` found the manifests using the `default` namespace and missing most container-level
  hardening; the app's actual write needs (SQLite file, temp files) needed explicit volumes once the root
  filesystem became read-only.
- **Files**: `kubernetes/namespace.yaml` (new), `kubernetes/deployment.yaml`, `kubernetes/service.yaml`,
  `kubernetes/ingress.yaml`, `kubernetes/network-policy.yaml`, `helm/devsecops-app/values.yaml`,
  `helm/devsecops-app/templates/deployment.yaml`
- **Tests**: YAML-validated with PyYAML; `checkov -d kubernetes --framework kubernetes` — went from a mix of
  passing/failing checks (12 failed at baseline review) to 93 passed / 1 failed (image digest pinning,
  documented as requiring a real published image — see `docs/SECURITY.md` Section 6). `helm template` could
  not run (no `helm` binary in this sandbox) — chart reviewed by hand.
- **Result**: Fixed (93/94 on plain manifests); Helm chart changes mirror the same fixes but were not rendered/
  verified with the real `helm` binary in this sandbox.
- **Remaining Issues**: Run `helm template devsecops-app ./helm/devsecops-app` on a machine with Helm installed
  and diff against the plain manifests to confirm they stay equivalent.

### 2026-09-02 — Change #10: Documentation
- **Change**: Wrote `docs/BASELINE.md`, `docs/GAP_ANALYSIS.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/PRD.md`,
  `docs/TRD.md`, `docs/SECURITY.md`, `docs/FLOW.md`, `docs/ARCHITECTURE.md`, `docs/FINAL_AUDIT.md`, and this
  `CONTEXT.md`; corrected `README.md` (removed the non-existent `chaos/` reference, documented the new stages/
  services/env-var requirements).
- **Reason**: None of these existed before this engagement; the README overstated repository contents in one
  place.
- **Files**: all files under `docs/`, `CONTEXT.md`, `README.md`
- **Tests**: Cross-checked every claim in every document against the actual code/config in this repository at
  the time of writing (see `docs/FINAL_AUDIT.md` "Documentation Completed" for the explicit cross-check).
- **Result**: Complete.
- **Remaining Issues**: None — keep these synchronized with any future code change (see "How to Continue
  Development" above).
