# Product Requirements Document (PRD)

## 1. Project Overview
`DevSecOps-CI-CD-Project` is an AI-augmented, security-first CI/CD pipeline for a small Python (Flask) web
application. It exists to demonstrate — and to genuinely implement, not just describe — a modern DevSecOps
practice: security scanning at every pipeline stage, AI/LLM assistance in code review and documentation, ML
experiment tracking for that AI usage, policy-as-code enforcement, and observable, containerized deployment to
Kubernetes. It was built to satisfy Al-Nafi International College's EduQual Level 6 Diploma in AIOPS exam topic
"Implementing AI-Augmented DevSecOps Pipeline with LLMOps, Security Intelligence, and Regulatory Compliance."

## 2. Problem Statement
Manual code review is slow and inconsistent; AI-generated and human-written code both carry unreviewed risk;
open-source dependencies introduce vulnerabilities that go unnoticed without automated scanning; AI/LLM usage in
a pipeline is rarely versioned or audited like any other production asset; and proving compliance by hand does
not scale. This project addresses each of these directly rather than describing them in the abstract.

## 3. Project Goals
- Automate the software delivery pipeline (build, test, security-scan, deploy) end to end.
- Integrate AI/LLM assistance into that pipeline for code review, vulnerability triage, and documentation —
  without letting AI output bypass human review or CI gates.
- Make every security control observable: reports are archived artifacts, not claims.
- Track every AI/LLM pipeline run (model, duration, findings) as an auditable, versioned event.

## 4. Objectives
1. A working Flask application with a real, if small, attack surface to secure (data writes, search, auth).
2. A CI/CD pipeline (Jenkins) that runs lint, tests, SAST, SCA, secret scanning, IaC scanning, container
   scanning, an OPA policy gate, AI analysis, and DAST — in that dependency order.
3. Three distinct AI/LLM integrations (LangChain+Ollama code review, Hugging Face Transformers vulnerability
   triage, LlamaIndex+Ollama documentation generation), each with MLflow tracking and a working non-AI fallback.
4. Kubernetes manifests and an equivalent Helm chart that pass an automated IaC security scan.
5. Observability (Prometheus, Grafana, Loki+Promtail) that actually receives data from the running app, not just
   configuration files that assume it will.
6. Documentation (this set) that states plainly what is implemented, partially implemented, or planned — never
   claims completion it cannot back up.

## 5. Target Users
- **The student/engineer operating this pipeline** (primary user) — needs to run scans locally, understand
  failures, and extend the pipeline.
- **An examiner/reviewer** — needs to verify the architecture matches the presentation and the requirements
  document, and probe specific technical decisions.
- **A future engineer inheriting this repository** — needs `CONTEXT.md` and this document set to resume work
  without re-deriving the whole system from source.

## 6. User Stories
- As a developer, I can push a change and have the pipeline run unit tests, lint, and every security scanner
  automatically, so I find problems before a human reviewer has to.
- As a security reviewer, I can open `reports/` after a pipeline run and see machine-readable output from
  Bandit, Semgrep, Snyk, OWASP Dependency-Check, Trivy, checkov, gitleaks, and OPA — all in one place.
- As an AI/ML practitioner, I can open MLflow and see every AI pipeline run (code review, vulnerability triage,
  doc generation) with its model, duration, and result, so AI usage is auditable exactly like a training run
  would be.
- As an operator, I can query Grafana and actually see request-rate metrics and application logs for the
  running service, not an empty dashboard.
- As an examiner, I can read `docs/SECURITY.md` and get an honest answer, control by control, about which of
  the presentation's claims (TLS 1.3, OAuth2, JWT, mTLS, RBAC) are implemented in this repository today versus
  planned.

## 7. Functional Requirements
- FR1: The application exposes `/`, `/health`, `/users` (GET/POST), `/search` (GET), `/metrics`.
- FR2: `POST /users` and `/search` validate and length-limit input and reject malformed data with 400.
- FR3: `POST /users` requires an API key (`X-API-Key`) when `APP_API_KEY` is configured.
- FR4: The CI pipeline runs, in order: checkout → install deps → lint → unit tests → SAST → SonarQube → secret
  scan → SCA → AI review/analysis/docs → MLflow logging → container build → container scan → IaC scan → OPA
  gate → security gate → deploy → DAST → post-deploy verification.
- FR5: Each AI/LLM script produces a JSON (or Markdown) report even when its live model/service is unavailable
  (documented fallback behavior), so the pipeline never hard-fails purely because Ollama/MLflow isn't running.
- FR6: Kubernetes manifests and the Helm chart deploy the app with non-root execution, resource limits, health
  probes, and NetworkPolicy-restricted traffic.

## 8. Non-Functional Requirements
- **Reproducibility**: `pip install -r app/requirements.txt` and `pip install -r ai-agents/requirements.txt`
  must succeed from a clean environment (this was broken at baseline — see `docs/BASELINE.md` — and is fixed).
- **Resilience**: no AI/observability integration failure should crash the application or silently hang a CI
  stage (the MLflow connection-hang bug found and fixed in this engagement is the concrete example).
- **Traceability**: every AI run, every security scan, and every deploy is logged/archived, not ephemeral.

## 9. Security Requirements
See `docs/SECURITY.md` for the full treatment. Summary: no hardcoded secrets, parameterized SQL only, an
API-key gate on writes, rate limiting, secret scanning in CI, dependency/container/IaC scanning in CI, an OPA
admission policy denying root/`:latest`/unbounded-resource pods, and documented (not fabricated) TLS/OAuth2/JWT
posture.

## 10. DevSecOps Requirements
Security checks run at every CI stage, before deploy — see `docs/FLOW.md` "CI/CD Flow". Scans are archived as
artifacts. Enforcement (fail-the-build) is opt-in via `ENFORCE_SECURITY`, matching this project's documented
exam/demo-cycle philosophy, with a single aggregated `Security Gate` stage making that decision instead of it
being scattered per-tool.

## 11. AI/LLM Requirements
Three integrations, each independently useful and each with a working fallback (see `docs/TRD.md` "LLM
Architecture" for detail): LangChain+Ollama(CodeLlama) code review, Hugging Face Transformers vulnerability
triage (with a documented model-choice limitation — see `docs/SECURITY.md`), and LlamaIndex+Ollama(Llama3)+HF
embeddings documentation generation. MLflow tracks every run.

## 12. Cloud Requirements
Terraform provisions AWS governance/security primitives (KMS, CloudTrail, GuardDuty, Security Hub, Secrets
Manager, an IAM role) in `ap-south-1`, parameterized via `terraform/variables.tf`. It assumes an
externally-provisioned Kubernetes cluster — provisioning that cluster (EKS/VPC/networking) is explicitly out of
scope and documented as such, not silently missing.

## 13. Performance Requirements
No formal SLA is defined (this is an exam/demo-scale project, not a production service with contracted
throughput). Resource requests/limits are set (100m/500m CPU, 128Mi/512Mi memory) as a reasonable default for a
small Flask+SQLite service; load testing was not performed and is listed as a future improvement.

## 14. Availability Requirements
The Kubernetes Deployment runs 2 replicas with liveness/readiness probes. SQLite as the datastore is a
single-writer, single-file store — acceptable for a demo, explicitly not a highly-available production database
(see `docs/TRD.md` "Database Architecture" and "Known Limitations" for the honest tradeoff).

## 15. Scalability Requirements
Horizontal scaling of the Flask app is possible (stateless except for the SQLite file), but the current
in-process rate limiter and SQLite backend do not coordinate across replicas — documented as a known limitation
requiring a shared store (Redis for rate limiting, a real RDBMS for data) before scaling beyond one replica in
any way that matters.

## 16. Observability Requirements
Prometheus scrapes `/metrics`; Grafana visualizes it; Promtail ships container logs (including the app's
structured request logs) to Loki, which Grafana's "Application Security Logs" panel queries. This chain was
broken (no Loki container, no Promtail) at baseline and is fixed and documented in `docs/GAP_ANALYSIS.md`.

## 17. Compliance Considerations
ISO/IEC 42001 (AI governance), NIST AI RMF, and GDPR are the three frameworks the requirements document names.
This project supports alignment (versioned AI runs via MLflow, documented model provenance, no PII collected by
the sample app beyond a username/email a user submits themselves, data-retention notes in `docs/SECURITY.md`)
but does **not** claim formal certification — no DPO sign-off, no formal audit, no data protection impact
assessment exists or is claimed to exist. See `docs/SECURITY.md` "Compliance Alignment" for the honest,
control-by-control mapping.

## 18. Constraints
- Development/verification for this engagement happened in a sandboxed environment without a Docker daemon,
  Kubernetes cluster, live Jenkins agent, live Ollama server, or AWS credentials — see `docs/BASELINE.md`
  "Not Verified" for exactly what that means for confidence level per component.
- This is a single-service, single-database demo scale project, not a multi-team production system.

## 19. Assumptions
- An operator running this pipeline for real has (or will provision) a Kubernetes cluster, a Jenkins agent with
  Docker access, and valid tokens (Snyk, SonarQube) as documented in `.env.example`.
- The AI/LLM stages are expected to run in "fallback mode" in most CI environments (no local Ollama server) and
  that is treated as normal operation, not a failure.

## 20. Acceptance Criteria
- `pytest app/tests -v` passes with 0 failures (verified: 12/12 pass, 97% coverage — see `docs/BASELINE.md` and
  `docs/FINAL_AUDIT.md`).
- `bandit`, `semgrep` run clean against documented/accepted findings only.
- Every `ai-agents/*.py` script runs to completion (fallback or live) without raising an unhandled exception.
- `docker-compose.yml`, all Kubernetes manifests, and the Helm chart parse as valid YAML/templates.
- checkov IaC scan: Terraform 48/54 checks pass (6 documented accepted-scope gaps); Kubernetes 93/94 checks pass
  (1 documented accepted gap — image digest pinning, which requires an image that has actually been published).
- Every documentation file in `docs/` reflects the actual implementation, cross-checked in `docs/FINAL_AUDIT.md`.

## 21. Future Improvements
- Replace SQLite with a real RDBMS and the in-process rate limiter with a shared (Redis) one before scaling
  beyond a single replica.
- Replace the sentiment-analysis-repurposed Hugging Face model with a purpose-built vulnerability-severity
  classifier.
- Provision the Kubernetes cluster itself via Terraform (currently assumed pre-existing).
- Implement a service mesh (Istio/Linkerd) for real mTLS pod-to-pod, and a real IdP for OAuth2/JWT, to close
  the gap between the presentation's aspirational security architecture and the current implementation.
- Add SNS-based CloudTrail delivery notifications, S3 access logging/cross-region replication, and Secrets
  Manager rotation (all currently documented accepted gaps in the Terraform IaC scan).
- Pin the Kubernetes Deployment's container image to an immutable digest once CI actually publishes one.
