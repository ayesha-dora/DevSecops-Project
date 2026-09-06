# Gap Analysis — AI-Augmented DevSecOps Pipeline

Source of requirements: `Ayesha exam req.pdf` ("Topic 2: Implementing AI-Augmented DevSecOps Pipeline with
LLMOps, Security Intelligence, and Regulatory Compliance", Al-Nafi International College, EduQual Level 6,
Diploma in AIOPS) and `ayesha ppt.pdf` (the student's own oral-presentation deck, which commits to specific
implementation claims — TLS 1.3, OAuth 2.0, JWT, mTLS, RBAC, ISO/IEC 42001, NIST AI RMF, GDPR). This document
compares both against the repository as received (see `docs/BASELINE.md`) and states, item by item, what exists,
what's missing, what's broken, and what's insecure.

## Current Implementation (what already exists and works)

- A Flask REST API (`app/app.py`) with `/`, `/health`, `/users` (GET/POST), `/metrics` (Prometheus), backed by
  SQLite, using parameterized queries throughout (no SQL injection in the shipped code).
- A test suite (`app/tests/test_app.py`, pytest) covering 5 of 6 written test cases successfully.
- A production-oriented `Dockerfile`: slim base image, non-root user matching the Kubernetes `runAsUser`,
  gunicorn instead of the dev server.
- Three real AI/LLM integrations under `ai-agents/`, each with a working degrade-to-static fallback:
  - `code_reviewer.py` — LangChain + local Ollama (CodeLlama) for AI code review.
  - `hf_code_analyzer.py` — Hugging Face Transformers pipeline enriching Bandit findings.
  - `code_indexer.py` — LlamaIndex + Ollama (Llama3) + a Hugging Face embedding model for auto-generated docs.
  - `mlflow_logger.py` — logs every AI run (params + metrics) to an MLflow tracking server.
- A Jenkins pipeline (`Jenkinsfile`) with real stages: checkout, SAST (Bandit + Semgrep), dependency scanning
  (Snyk + OWASP Dependency-Check), AI code review, container build + Trivy scan, an OPA compliance gate, a
  Kubernetes deploy step, and an OWASP ZAP DAST stage.
- A real OPA/Rego admission policy (`security/policy.rego`) with a working test harness and both a
  policy-violating and policy-compliant example manifest.
- Kubernetes manifests and an equivalent parameterized Helm chart (Deployment, Service, Ingress, NetworkPolicy)
  with resource limits, probes, and `runAsNonRoot`.
- Terraform for AWS governance/security primitives (KMS, CloudTrail, GuardDuty, Security Hub, Secrets Manager,
  an IAM role) targeting `ap-south-1`.
- Prometheus + Grafana + Loki configuration, plus a `docker-compose.yml` that stands the whole toolchain
  (Jenkins, SonarQube, Prometheus, Grafana, MLflow, ZAP) up locally.
- A long, mostly accurate `README.md`.

This is a substantially more complete starting point than a typical "demo" repository — the priority in this
engagement was to close real gaps, not rebuild what already works.

## Required Features (from the requirements document)

1. CI/CD pipeline with security checks at every stage (Jenkins or GitLab CE). ✅ have Jenkins.
2. LLM integration for code generation, code review, documentation, and debugging (Hugging Face
   Transformers/LangChain/LlamaIndex or similar). ✅ have all three named frameworks.
3. MLflow or Kubeflow for AI model management. ✅ have MLflow.
4. Automated security tooling: Trivy (container), Semgrep or Bandit (SAST), OWASP Dependency-Check (SCA). ✅ have
   all three, plus Snyk as a bonus.
5. SonarQube Community Edition and OWASP ZAP for code quality and DAST. ✅ present (SonarQube config + ZAP
   runner) but ⚠️ SonarQube was **not wired into the Jenkins pipeline at all** — see Broken Features.
6. Prometheus + Grafana for observability. ✅ present.
7. Network Flow Diagram, Data Flow Diagram, System-Level Architecture Diagram. ⚠️ exist only as PPT slide
   graphics for the oral exam, not as versioned diagrams in the repository/documentation — now added as Mermaid
   diagrams in `docs/ARCHITECTURE.md` and `docs/FLOW.md`.
8. GitHub repository containing pipeline configs, AI integration code, security configs, and documentation,
   "structured clearly and reproducible." ✅ structure exists; ⚠️ reproducibility was broken by the
   `pytest-cov==4.1.1` bad pin (Broken Features) and by the unpinned runtime `pip install` calls in `ai-agents/`.
9. Alignment with ISO/IEC 42001 (AI governance), NIST AI RMF, and GDPR. ⚠️ README asserts a governance narrative;
   the presentation goes further and asserts TLS 1.3, OAuth 2.0, JWT, mTLS, and RBAC are implemented. None of
   those five specific controls existed in the code as received — see Security Problems below. This gap matters
   most: an examiner who reads the slides and then the repo will find the claims and the code disagree.

## Missing Features

| # | Missing item | Where it should live | Status after this engagement |
|---|---|---|---|
| 1 | `/search` endpoint (referenced by the existing test) | `app/app.py` | Implemented — parameterized `LIKE` query, input length/charset validation |
| 2 | Authentication on state-changing endpoints | `app/app.py` | Implemented — API-key check on `POST /users`, documented as a demo-grade control, not enterprise IAM |
| 3 | Structured application logging | `app/app.py` | Implemented — request logging (method, path, status, latency), no bodies/PII/secrets logged |
| 4 | Rate limiting | `app/app.py` | Implemented — lightweight in-process limiter on `POST /users` and `/search`, documented limitation for multi-replica deployments |
| 5 | Secret scanning in CI | `security/`, `Jenkinsfile` | Implemented — gitleaks config + Jenkins stage |
| 6 | IaC scanning (Terraform/Kubernetes) | `security/`, `Jenkinsfile` | Implemented — `tfsec`/`checkov`-based stage (best-effort; documented as requiring the CI agent to have the binary or Docker) |
| 7 | Unit test + lint stage in CI | `Jenkinsfile` | Implemented — pytest and flake8 stages added before SAST |
| 8 | SonarQube stage in CI | `Jenkinsfile` | Implemented — `sonar-scanner` stage wired to the existing `sonar-project.properties` |
| 9 | Log shipping to Loki (Promtail) | `monitoring/`, `docker-compose.yml` | Implemented — Promtail service + config |
| 10 | `.env.example` documenting required secrets/config | repo root | Implemented |
| 11 | Pinned AI/LLM dependency versions | `ai-agents/requirements.txt` | Implemented — replaces runtime `os.system(pip install ...)` with a documented, pinned requirements file |
| 12 | Container `HEALTHCHECK` | `app/Dockerfile` | Implemented |
| 13 | `chaos/` LitmusChaos example (README references it, doesn't exist) | `chaos/` | Documented as **not implemented** (README corrected instead of inventing untested chaos manifests — see Documentation Problems) |
| 14 | mTLS / OAuth2 / JWT / TLS 1.3 as literally described on the slides | mesh + app + ingress | **Not implemented** — this requires a service mesh (Istio/Linkerd) and an identity provider that are out of scope for a single-VM/sandbox engagement; documented honestly in `docs/SECURITY.md` and `docs/GAP_ANALYSIS.md` as "Planned / requires external infrastructure," with the achievable subset (Ingress TLS termination, an API-key control standing in for token auth, NetworkPolicy-based pod isolation) implemented instead |

## Broken Features

1. **`pip install -r app/requirements.txt` failed outright** — `pytest-cov==4.1.1` is not a published PyPI
   release. This meant nobody could reproduce a clean install of the stated dependencies. **Fixed** → `4.1.0`.
2. **`app/tests/test_app.py::test_search` failed** — tested a route that did not exist. **Fixed** by implementing
   the route rather than deleting the test.
3. **Jenkins pipeline was silently incomplete**: `hf_code_analyzer.py` and `code_indexer.py` were never called,
   and `mlflow_logger.py` ran before those two reports existed, so two of the three MLflow AI runs it tries to
   log (`hf_analysis.json`, `AUTO_GENERATED_README.md`) were always missing in a real run. **Fixed** — see
   `Jenkinsfile` changes in `CONTEXT.md`.
4. **SonarQube was configured but never invoked** — `docker-compose.yml` runs it and
   `sonarqube/sonar-project.properties` configures it, but no Jenkins stage ever ran `sonar-scanner`. **Fixed.**
5. **Loki had no log source** — configured to receive logs, nothing sent any. **Fixed** with Promtail.
6. **README overstated repo contents** (`chaos/` directory referenced but absent). **Fixed** — README corrected
   to say chaos engineering is planned/not implemented rather than implied present.

## Security Problems

- No authentication/authorization anywhere in the API — anyone who can reach the service can write to the
  database. *(Fixed: API key on write endpoints — documented as demo-grade.)*
- No rate limiting — trivial DoS/spam against `/users` and any future `/search`. *(Fixed: basic limiter.)*
- No input validation beyond "field present" — arbitrary-length strings accepted into SQLite. *(Fixed: length
  and character-class checks.)*
- `ai-agents/*.py` install unpinned Python packages at runtime via `os.system("pip install ...")` if imports
  fail — a software-supply-chain risk (non-reproducible, no integrity checking, silently pulls "latest").
  *(Fixed: pinned `ai-agents/requirements.txt`; scripts now fail closed to their static fallback instead of
  self-installing.)*
- `ai-agents/hf_code_analyzer.py` loads `distilbert-base-uncased-finetuned-sst-2-english` from the Hugging Face
  Hub with no pinned revision — a mutable reference; a future change to that model card would silently change
  pipeline behavior. *(Fixed: pinned `revision` hash and documented the mismatch — this is a **sentiment**
  model repurposed as a confidence proxy for vulnerability triage, not a security-purpose-built model; this is
  called out explicitly as a design limitation in `docs/SECURITY.md`, not hidden.)*
- Grafana ships with a widely-known default admin password (`admin123`) baked into `docker-compose.yml`.
  *(Fixed: moved to `${GRAFANA_ADMIN_PASSWORD}` env var, `.env.example` added with a placeholder and a comment
  to change it before any non-local use.)*
- No secret-scanning gate exists to catch a future accidental credential commit. *(Fixed: gitleaks.)*
- Security scan stages in `Jenkinsfile` are all non-blocking (`|| true`) by explicit design choice documented in
  the README, gated behind an `ENFORCE_SECURITY` parameter that defaults to `false`. This is a legitimate
  "shift-left, don't block dev velocity in early exam/demo cycles" pattern, but it means the pipeline currently
  cannot itself prove enforcement — this is documented plainly (not claimed as "security gate enforced") in
  `docs/SECURITY.md`, and the aggregated Security Gate stage added in this engagement makes the all-or-nothing
  enforcement decision explicit and centralized rather than scattered per-tool.
- No LLM-specific input/output guardrails: `code_reviewer.py` sends the full contents of `app/app.py` to a
  locally-hosted model with no size cap; if this pattern were reused for user-supplied code, prompt injection via
  code comments is a real risk. Documented in `docs/SECURITY.md` LLM Security section, with a recommended size
  cap and prompt-injection caution added.

## DevOps Problems

- No unit-test or lint stage in CI (fixed).
- No SonarQube stage despite being provisioned (fixed).
- No secret-scanning or IaC-scanning stage (fixed).
- `Jenkinsfile` used `${env.PATH}` and a `DOCKER_HOST` pointing at `host.docker.internal`, which only resolves
  correctly depending on the Jenkins agent's own container networking — documented as an environment-specific
  assumption in `docs/TRD.md` rather than silently left unexplained.
- No versioned/tagged artifact strategy beyond `${BUILD_NUMBER}` for the app image — acceptable for a student
  exam pipeline, called out as a "future improvement" (semantic versioning / Git SHA tags) rather than treated as
  broken.

## Architecture Problems

- Terraform provisions AWS governance controls (KMS, CloudTrail, GuardDuty, Security Hub, Secrets Manager, an
  IAM role) but not the EKS cluster / VPC / networking that the Kubernetes manifests assume exists. This is a
  reasonable scope boundary for an exam project (a full VPC+EKS Terraform stack is a multi-day undertaking on its
  own) but was undocumented. Documented now in `docs/TRD.md` and `docs/ARCHITECTURE.md` as an explicit trust
  boundary/assumption: "an existing Kubernetes cluster is assumed; Terraform manages governance and secrets
  around it, not the cluster itself."
- The AI agents are independent scripts invoked as CLI stages rather than a single orchestrated service —
  consistent with "LangChain chains the AI steps together" from the slides only in the loose sense that each
  step is chained via the Jenkins pipeline sequence, not via actual LangChain `Chain`/`Runnable` composition
  across scripts. This is accurately described (not overclaimed) in `docs/TRD.md`.

## Documentation Problems

- `README.md` referenced a `chaos/` directory that does not exist. Fixed.
- No PRD, TRD, SECURITY, FLOW, ARCHITECTURE, GAP_ANALYSIS, IMPLEMENTATION_PLAN, BASELINE, or CONTEXT documents
  existed anywhere in the repository — all created in this engagement.
- The oral-presentation slide deck (`ayesha ppt.pdf`) asserts several controls (TLS 1.3 everywhere, OAuth 2.0,
  JWT for AI service auth, mTLS pod-to-pod, RBAC) that are aspirational/architectural intent rather than
  implemented code. `docs/SECURITY.md` and `docs/TRD.md` now state plainly, control by control, which of these
  are implemented, which are partially implemented (e.g., Ingress TLS termination exists; TLS 1.3 specifically
  is an Nginx Ingress controller configuration choice outside this repo, not code here), and which are planned
  and require infrastructure (a service mesh, an IdP) this repository does not provision.

## LLM Problems

| Risk | Current state | Mitigation applied |
|---|---|---|
| Prompt injection via reviewed source code | `code_reviewer.py` sends raw file contents into the prompt with no sanitization | Documented; recommend size cap + comment-stripping if this is ever pointed at untrusted/external code (not needed today since it only reviews the repo's own `app/app.py`) |
| Sensitive data exposure via prompts/outputs | Reports are written to `reports/*.json` and archived by Jenkins; no secrets currently flow through this path | Logging guidance added: never point these scripts at files containing real credentials/PII |
| Model supply-chain risk (unpinned HF model, unpinned pip installs at runtime) | See Security Problems | Pinned `ai-agents/requirements.txt`; pinned HF model revision |
| Unsafe/unvalidated model output consumed downstream | AI review output is written to a report file for human/CI review, not auto-applied to code or auto-merged | Already safe by design (human-in-the-loop); documented explicitly so it isn't accidentally automated later without review |
| Excessive resource consumption | Hugging Face model download (~500MB) and local Ollama inference have no timeout/circuit breaker beyond LangChain's own `timeout=120` | Documented as a known limitation; recommend a CI resource quota if adopted beyond a single exam VM |
| Using a sentiment-analysis model to score vulnerability "confidence" | `hf_code_analyzer.py` uses `distilbert-base-uncased-finetuned-sst-2-english`, a positive/negative sentiment classifier, as a stand-in confidence score for security findings | Left in place (per "do not unnecessarily replace working LLM functionality") but called out honestly as a semantic mismatch/limitation in `docs/SECURITY.md`, with a documented recommendation to replace it with a purpose-built classifier if this moves beyond a teaching exercise |

## Priority Table

| Priority | Issue | Requirement | Impact | Proposed Solution |
|---|---|---|---|---|
| Critical | `pytest-cov==4.1.1` invalid pin breaks all installs | "reproducible" repo (req. §11) | Nobody can build the project from a clean clone | Pin to `4.1.0` (done) |
| Critical | No authentication on write endpoints | Security requirements throughout | Anyone can write arbitrary data | API-key auth on `POST /users` (done) |
| High | Missing `/search` route breaks the shipped test suite | "automated testing" (req. §3.1) | CI test stage would always fail once added | Implement route securely (done) |
| High | Secret scanning absent from pipeline | "prevent secrets entering repo" (master instructions) | A future accidental credential commit would go undetected | gitleaks stage (done) |
| High | Jenkinsfile omits 2 of 3 AI scripts + SonarQube | "LLM integration...code review, documentation" (req. §3.2), SonarQube required tool (req. §5.1) | Pipeline doesn't demonstrate the full AI/quality toolchain it claims to have | Add missing stages (done) |
| Medium | Unpinned runtime `pip install` in AI scripts | Supply-chain security (master instructions §15) | Non-reproducible builds, silent version drift | Pin `ai-agents/requirements.txt` (done) |
| Medium | Loki receives no logs (no Promtail) | Observability requirement (req. §5.4) | Grafana "Application Security Logs" panel is always empty | Add Promtail (done) |
| Medium | Grafana default password in compose file | Secrets management (master instructions §16) | Trivially guessable local-admin credential | Move to env var (done) |
| Medium | IaC not scanned | DevSecOps requirement (master instructions §14, §11) | Misconfigured Terraform/K8s could ship undetected | Add `tfsec`/`checkov` stage (done, best-effort) |
| Low | No container `HEALTHCHECK` | Container security best practice (master instructions §12) | `docker run` alone has no liveness signal outside Kubernetes | Add `HEALTHCHECK` (done) |
| Low | README references non-existent `chaos/` dir | Documentation accuracy | Misleads a reader about repo contents | Correct README wording (done) |
| Low | Slide-deck claims of TLS 1.3 / OAuth2 / JWT / mTLS / RBAC not literally implemented | Alignment between presentation and repo | Examiner may probe a control that isn't there | Document actual vs. planned state explicitly in SECURITY.md/TRD.md (done); do not fabricate the controls just to match the slide |
