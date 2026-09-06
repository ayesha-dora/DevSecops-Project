# Technical Requirements Document (TRD)

This document describes how the system is actually built, as of this engagement. Where the presentation deck
(`ayesha ppt.pdf`) describes a control this repository does not implement, that is stated explicitly rather than
smoothed over — see each section's "Status" note.

## 1. System Architecture
A single Flask application, containerized, deployed to Kubernetes behind an Nginx Ingress, with a Jenkins
pipeline that builds/tests/scans/deploys it and three independent AI/LLM helper scripts that assist the pipeline
(not the running application — the AI scripts are CI-time tools, not a runtime API the app calls). See
`docs/ARCHITECTURE.md` for diagrams.

## 2. Component Architecture
- `app/` — the Flask application and its tests.
- `ai-agents/` — four independent CLI scripts invoked as Jenkins stages: `code_reviewer.py`,
  `hf_code_analyzer.py`, `code_indexer.py`, `mlflow_logger.py`.
- `security/` — scanner configs (Bandit, Semgrep, Snyk, Trivy, gitleaks) + the OPA policy and its test harness
  + `security_gate.py` (new in this engagement — aggregates scan results into one pass/fail decision).
- `kubernetes/` + `helm/devsecops-app/` — two equivalent ways to deploy the same application (plain manifests
  and a parameterized Helm chart).
- `terraform/` — AWS governance/security primitives, not the cluster itself.
- `monitoring/` — Prometheus, Loki, and (new in this engagement) Promtail configuration; Grafana dashboard JSON.
- `docker-compose.yml` — stands up the whole local toolchain (app, Jenkins, SonarQube, Prometheus, Grafana,
  MLflow, ZAP, Loki, Promtail) for local development/demo.

## 3. Technology Stack
Python 3.11 (Flask, gunicorn, sqlite3, prometheus_client) · Jenkins (Groovy Jenkinsfile) · Docker · Kubernetes
1.2x-compatible manifests + Helm 3 · Terraform ≥1.3 (AWS provider ~5.0) · LangChain + langchain-community +
Ollama (CodeLlama) · Hugging Face Transformers (a DistilBERT sentiment model, repurposed — see Section 7) ·
LlamaIndex + Ollama (Llama3) + Hugging Face embeddings (`BAAI/bge-small-en-v1.5`) · MLflow · Bandit, Semgrep,
Snyk, OWASP Dependency-Check, Trivy, gitleaks, checkov, OPA/Rego, OWASP ZAP · Prometheus, Grafana, Loki,
Promtail.

## 4. Application Architecture
`app/app.py` is a single-file Flask app. Routes: `/` (info), `/health` (liveness/readiness target), `/users`
GET (list) and POST (create, API-key gated), `/search` GET (parameterized `LIKE` query), `/metrics`
(Prometheus exposition). Structured logging via `logging` (method/path/status/duration, no bodies/secrets) is
attached via `before_request`/`after_request` hooks. A simple in-process token-bucket rate limiter guards
`POST /users` and `/search`. **Status: implemented and tested** (12/12 pytest cases, 97% line coverage).

## 5. API Architecture
REST/JSON over HTTP. No versioning scheme (`/v1/...`) exists — acceptable at this scale, listed as a future
improvement if the API surface grows. Errors return a JSON `{"error": "..."}` body with an appropriate 4xx code
(400 validation, 401 missing key, 403 wrong key, 429 rate-limited).

## 6. Database Architecture
SQLite, single file (`APP_DB`, default `/tmp/users.db`, moved to a mounted `/data` volume in the Kubernetes
manifests since the container filesystem is now read-only — see Section 18). One table (`users`: id, username,
email). **Status/limitation**: SQLite is a single-writer store; this is fine for a demo/exam application and
explicitly not represented as production-grade high-availability storage — see `docs/PRD.md` Section 14.

## 7. LLM Architecture
Three independent scripts, each invoked as its own Jenkins stage, each with a working fallback:

- **`code_reviewer.py`** — reads `app/app.py`, sends it (capped at 20,000 chars — added in this engagement as a
  defense-in-depth prompt-size guard) to a local Ollama server running CodeLlama via
  `langchain_community.llms.Ollama` + LCEL (`prompt | llm`). On any import/connection failure, writes a static
  fallback report kept in sync with the actual current state of `app/app.py` (also fixed in this engagement —
  the fallback previously described SQL-injection/no-validation issues that had already been resolved,
  which was itself a documentation-accuracy bug).
- **`hf_code_analyzer.py`** — reads `reports/bandit-report.json`, runs each finding's text through a Hugging
  Face `text-classification` pipeline (`distilbert-base-uncased-finetuned-sst-2-english`) and uses the
  classifier's confidence score as a proxy "priority" (HIGH/MEDIUM/LOW). **Known limitation, documented not
  hidden**: this model is a general-purpose positive/negative sentiment classifier, not a security-severity
  classifier — it was not trained for this task. It is kept per this engagement's instruction not to replace
  working functionality; `docs/SECURITY.md` recommends a purpose-built replacement.
- **`code_indexer.py`** — uses LlamaIndex (`SimpleDirectoryReader` + `VectorStoreIndex`) over `app/`, with Ollama
  (Llama3) as the LLM and a Hugging Face embedding model (`BAAI/bge-small-en-v1.5`), to answer four fixed
  questions (overview, endpoints, security, setup) and write `docs/AUTO_GENERATED_README.md`.
- **`mlflow_logger.py`** — reads whatever of the above three reports exist and logs each as an MLflow run
  (params: framework/model/build number; metrics: duration, issue counts). **Bug found and fixed in this
  engagement**: this script could hang indefinitely if the MLflow tracking server was unreachable, because
  MLflow's own HTTP retry/backoff ignores the documented timeout env var; a hard wall-clock timeout
  (`SIGALRM`, 10s default) was added so an unreachable server now fails fast and non-fatally instead of
  stalling the Jenkins stage.

**Orchestration honesty note**: the presentation describes "LangChain chains the AI steps together." In this
implementation, the three AI scripts are independently invoked, in sequence, by the Jenkinsfile — they are
chained by pipeline ordering, not by a single LangChain `Runnable`/`Chain` object composing all three. This is
accurately described here rather than overclaimed.

## 8. Hugging Face Integration
Two distinct HF touchpoints: `hf_code_analyzer.py`'s classification pipeline (Section 7) and
`code_indexer.py`'s `HuggingFaceEmbedding` (`BAAI/bge-small-en-v1.5`) used by LlamaIndex for retrieval. Both are
loaded via the standard `transformers`/`llama-index-embeddings-huggingface` APIs; no custom/remote code
execution (`trust_remote_code`) is used anywhere. Model revision pinning is supported via `HF_MODEL_REVISION`
(added in this engagement) for the classification model; if unset it defaults to `main` with a printed warning
(see `docs/SECURITY.md` "Model Supply Chain").

## 9. Model Inference Flow
See `docs/FLOW.md` "LLM Flow" for the end-to-end diagram. In short: Jenkins stage → script reads its input
(source file or Bandit report) → live model call with the documented fallback on failure → JSON/Markdown report
written to `reports/`/`docs/` → archived as a Jenkins artifact → `mlflow_logger.py` records the run.

## 10. Docker Architecture
`app/Dockerfile`: `python:3.11-slim` base, build deps installed then discarded from the final layer via
`--no-cache-dir`, non-root user (`appuser`, UID 10001, matching the Kubernetes `runAsUser`), gunicorn (not the
Flask dev server) as the entrypoint, and (added in this engagement) a `HEALTHCHECK` hitting `/health` so
`docker run`-only deployments (outside Kubernetes) still report health via `docker ps`/`docker inspect`.

## 11. CI/CD Architecture
Jenkins, declarative pipeline (`Jenkinsfile`). Stage order (rebuilt in this engagement to match what the repo
actually contains — see `docs/GAP_ANALYSIS.md` "Broken Features" for what was missing before):
Checkout → Install Dependencies → Lint → Unit Tests → SAST → SonarQube → Secret Scan → SCA → AI Review/Analysis/
Docs → MLflow Logging → Container Build → Container Scan → IaC Scan → OPA Gate → Security Gate → Deploy →
DAST → Post-Deployment Verification. Reports are archived (`archiveArtifacts`) regardless of pass/fail
(`always`). An `ENFORCE_SECURITY` boolean parameter (default `false`) controls whether the new aggregated
Security Gate stage fails the build on HIGH/CRITICAL findings or only reports them — this default-off,
opt-in-enforcement design is an explicit, documented choice carried over from the original pipeline's philosophy
(visibility first, blocking is opt-in), not an oversight.

**Environment-specific assumption, documented not hidden**: `DOCKER_HOST=tcp://host.docker.internal:2375` and
several `docker run --network devsecops ...` calls assume the Jenkins agent itself is a container on the same
Docker host as the `docker-compose.yml` toolchain (or an equivalent network setup). This works for the
documented local/demo topology; a different Jenkins agent topology (a VM, a Kubernetes-based Jenkins agent)
would need these adjusted — flagged here rather than left as an unexplained assumption.

## 12. DevSecOps Architecture
Security tooling runs at build time (SAST/SCA/secret/IaC/container scans) and at deploy time (OPA admission-style
policy check via the test harness, then a live DAST pass against the deployed instance) — "shift left," not
"security only at the end." See `docs/SECURITY.md` for the full Secure SDLC mapping.

## 13. Security Architecture
See `docs/SECURITY.md` (dedicated document, as required).

## 14. Authentication
**Application**: `POST /users` requires `X-API-Key` matching `APP_API_KEY` (added in this engagement — there
was no authentication anywhere in the app at baseline). This is a demo-grade shared-secret control, not OAuth2/
OIDC. **Status vs. presentation claim**: the presentation states developer access is authenticated via GitHub
OAuth 2.0 and AI-service requests use JWT — those are platform-level controls (GitHub's own auth, an API
gateway/service mesh in front of the AI scripts) that this repository does not itself provision; documented as
"Planned / requires external infrastructure" in `docs/SECURITY.md`, not implemented in code here.

## 15. Authorization
No role-based access control exists in the application (a single API key is all-or-nothing for the write
endpoint). Kubernetes RBAC is not defined in this repository (no `Role`/`RoleBinding`/`ClusterRole` manifests
exist) — the cluster's own default RBAC applies. Documented as a gap, not fabricated.

## 16. Secrets Management
No secret is hardcoded in source (verified by manual regex sweep — see `docs/BASELINE.md` and
`docs/GAP_ANALYSIS.md`). `.env.example` (new in this engagement) documents every environment variable the repo
uses, with placeholders only. `docker-compose.yml`'s Grafana password is now a required env var
(`${GRAFANA_ADMIN_PASSWORD:?...}`) instead of a hardcoded default. Terraform provisions an AWS Secrets Manager
secret (`devsecops/llm_api_key`) as the intended home for any real LLM API credentials, encrypted with a
customer-managed KMS key.

## 17. Network Security
`kubernetes/network-policy.yaml` (and the Helm equivalent) restrict ingress to the app's pod to the
ingress-controller and monitoring namespaces only, and restrict egress to DNS + HTTP/HTTPS. Ingress TLS
termination is configured (`kubernetes/ingress.yaml`, `nginx.ingress.kubernetes.io/ssl-redirect: "true"`) at the
Nginx Ingress controller level — the specific TLS version (the presentation names "TLS 1.3") is a controller
configuration choice made outside this repository (in the Ingress controller's own settings), not something
this repository's manifests set directly; documented honestly rather than asserted as code here.

## 18. Container Security
Non-root user, minimal base image, `HEALTHCHECK` (Section 10). Kubernetes pod/container `securityContext`
hardened in this engagement: `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`,
all Linux capabilities dropped, `readOnlyRootFilesystem: true` (with explicit `emptyDir` volumes for `/data` and
`/tmp` since the app needs to write its SQLite file and gunicorn/Flask temp files somewhere),
`automountServiceAccountToken: false` (the pod calls no Kubernetes API). Verified with `checkov`: 93/94 checks
pass on `kubernetes/`, the one remaining finding (image digest pinning) is a documented follow-up requiring an
image that has actually been published by CI, not fabricatable in this repository as-is.

## 19. Kubernetes Security
A dedicated `devsecops` namespace was added in this engagement (`kubernetes/namespace.yaml`) — the manifests
previously used the `default` namespace, which `checkov` (CKV_K8S_21) correctly flags. NetworkPolicy is
zero-trust by default (deny-all implicit, explicit allow rules only). No RBAC manifests are defined — the
cluster's default applies (documented gap, Section 15).

## 20. Infrastructure Architecture
Terraform manages AWS account-level governance/security (Section 21) around an assumed pre-existing Kubernetes
cluster. It does not provision compute, networking, or the cluster itself.

## 21. IaC Architecture
`terraform/`: `provider.tf` (region/tags, now variablized — `variables.tf`, new in this engagement),
`main.tf` (KMS key with an explicit policy, an encrypted+versioned+public-access-blocked+lifecycle-managed S3
bucket for CloudTrail logs, a multi-region CloudTrail trail with log-file validation and CloudWatch Logs
integration, GuardDuty, Security Hub, a KMS-encrypted Secrets Manager secret, an IAM role for Jenkins),
`outputs.tf`. Verified with `checkov`: 48/54 checks pass; the 6 remaining (SNS delivery notifications, S3 access
logging, S3 cross-region replication, Secrets Manager rotation, org-wide GuardDuty, S3 event notifications) are
documented accepted-scope gaps in `docs/SECURITY.md` — each would require infrastructure (an SNS topic and
subscriber, a second logging bucket, a rotation Lambda, an AWS Organizations context) disproportionate to an
exam-scope governance baseline, not silently unscanned.

## 22. Logging
Application: structured stdout logs (Section 4). AI scripts: `print()`-based stage logs (kept, since these are
CI-stage scripts whose "logs" are the Jenkins console output — not a design gap). Infrastructure: Promtail
(new in this engagement) ships all container logs, including the app's, to Loki via Docker service discovery;
CloudWatch Logs receives CloudTrail events (Section 21).

## 23. Monitoring
Prometheus scrapes `devsecops-app:5000/metrics` and Jenkins; Grafana visualizes it via the pre-built dashboard
JSON (HTTP request rate + the Loki-backed "Application Security Logs" panel, which is now actually populated —
see Section 22 and `docs/GAP_ANALYSIS.md`).

## 24. Testing Strategy
Unit tests only (`app/tests/test_app.py`, pytest, 12 cases, 97% line coverage of `app.py`). No integration or
load tests exist — listed as a future improvement (`docs/PRD.md` Section 21). Security testing is scanner-based
(SAST/SCA/container/IaC/secret) plus a policy-as-code test harness (`security/test_policy.sh` against two
example manifests) plus DAST (OWASP ZAP baseline scan).

## 25. Deployment Strategy
`kubectl apply` of plain manifests, or `helm install`/`helm upgrade` of the equivalent chart — both documented
in `README.md`. No blue/green or canary strategy is implemented; Kubernetes' default rolling update strategy
applies to the Deployment (2 replicas, no explicit `strategy:` override).

## 26. Backup/Recovery Strategy
Not implemented — SQLite lives on an `emptyDir` volume in the current Kubernetes manifests, meaning data does
NOT survive pod rescheduling. This is an explicit, documented limitation appropriate to a demo/exam scope, not a
silently-missing production feature. A real deployment would need a `PersistentVolumeClaim` at minimum, and
ideally a managed database instead of SQLite.

## 27. Disaster Recovery Considerations
None implemented beyond CloudTrail/GuardDuty/Security Hub visibility into the AWS account. No multi-region
failover, no automated backups. Documented as out of scope for this engagement.

## 28. Scalability
See `docs/PRD.md` Section 15 — the app is stateless-enough to scale horizontally except for its SQLite file and
its in-process rate limiter, both of which need a shared backing store before more than one replica's behavior
is fully correct.

## 29. Performance
No load testing was performed (see `docs/PRD.md` Section 13). Resource requests/limits are conservative
defaults suitable for the demo workload.

## 30. Threat Model
See `docs/SECURITY.md` "Threat Model" for the full table.

## 31. Security Controls
See `docs/SECURITY.md`.

## 32. Data Flow
See `docs/FLOW.md`.

## 33. LLM Security
See `docs/SECURITY.md` "LLM Security" (a required, dedicated section there).

## 34. Supply-Chain Security
`app/requirements.txt` and `ai-agents/requirements.txt` are both fully version-pinned (the latter added in this
engagement, replacing runtime `os.system("pip install ...")` calls with unpinned versions — a real
supply-chain fix, not cosmetic). `security/dependency-check.sh` and the Snyk stage scan for known-vulnerable
dependencies. `security/gitleaks.toml` (new) scans for accidentally committed credentials. checkov scans IaC.
Trivy scans the built container image.

## 35. Dependency Management
Two separate pinned requirement files by design: `app/requirements.txt` (what the running application needs —
kept minimal) and `ai-agents/requirements.txt` (what the CI-time AI stages need — kept separate so the
application's own dependency footprint and attack surface don't grow just because a CI helper script imports
`torch`).
