# Security Documentation

This document states, plainly and per-control, what is implemented, what is partially implemented, and what is
planned/requires infrastructure this repository does not provision. It intentionally does not restate the
presentation deck's aspirational architecture as fact — see each section for the actual current state.

## 1. Security Architecture
Defense in depth across four layers: (1) application — input validation, parameterized SQL, API-key auth on
writes, rate limiting; (2) pipeline — SAST/SCA/secret/container/IaC scanning before every deploy; (3) policy —
an OPA admission-style policy rejecting insecure Kubernetes manifests; (4) network/runtime — NetworkPolicy
zero-trust rules, non-root/read-only-filesystem/no-capabilities containers, Ingress TLS termination.

## 2. Secure SDLC
| Stage | Control |
|---|---|
| Development | Parameterized SQL, input validation, structured logging with no secret/PII leakage (code-level) |
| Commit | `.gitignore` excludes `.env`, reports, caches; `security/gitleaks.toml` scans for accidental secret commits |
| Pull Request / CI trigger | Jenkins `Checkout` stage; all scans below run on every build |
| Build | Lint (flake8), Unit Tests (pytest+coverage), SAST (Bandit+Semgrep), SonarQube |
| Test | Unit tests as above; policy test harness (`security/test_policy.sh`) validates the OPA policy itself against two fixture manifests |
| Containerization | Trivy image scan; non-root/minimal-base Dockerfile; `HEALTHCHECK` |
| Pre-Deploy | IaC scan (checkov on Terraform + Kubernetes); OPA compliance gate; aggregated Security Gate |
| Deployment | `kubectl apply`/`helm install`; NetworkPolicy + securityContext enforced by the cluster |
| Runtime | DAST (OWASP ZAP baseline) against the live instance; Prometheus/Grafana/Loki observability |

## 3. SAST
**Bandit** (`security/bandit.yaml`, severity ≥ medium) and **Semgrep** (`security/semgrep-rules.yaml`, 5 custom
rules: hardcoded passwords, string-concatenated SQL, `eval()`, shell injection, Flask debug mode) both run in
the `SAST` Jenkins stage. Current results against `app/`: Bandit reports 2 medium findings (binding to
`0.0.0.0` — expected/required inside a container; a `/tmp` default DB path — documented, and the actual default
is a demo convenience, not the production path, which should be a mounted volume as the Kubernetes manifests
now use). Semgrep reports 0 findings. Both were re-verified after every application change in this engagement
(see `docs/BASELINE.md` and `docs/FINAL_AUDIT.md`).

**SonarQube** (`sonarqube/sonar-project.properties`) is configured and (new in this engagement) actually
invoked by a Jenkins stage, reading the Bandit and coverage reports. A local SonarQube server is available via
`docker-compose.yml` for manual/CI use; the Jenkins stage gracefully skips with a clear message if
`sonar-scanner` isn't installed on a given agent rather than failing the whole build.

## 4. SCA (Software Composition Analysis)
Snyk (`security/snyk-config.json`, `severityThreshold: high`) and OWASP Dependency-Check
(`security/dependency-check.sh`, Docker-based) both scan `app/requirements.txt`. Enforcement (`exit 1` on
high/critical) is opt-in via `ENFORCE_SECURITY`, consolidated into the new `Security Gate` stage.
`ai-agents/requirements.txt` (new in this engagement) is scanned the same way `app/requirements.txt` is, closing
a gap where the AI pipeline's own dependencies were previously not pinned at all (installed ad hoc at runtime)
and therefore not scannable.

## 5. Secret Scanning
**New in this engagement** — `security/gitleaks.toml` (extends gitleaks' default rule set plus a generic
API-key/secret/token/password pattern, with an allowlist for documented placeholders like `.env.example`) and a
`Secret Scan` Jenkins stage. A manual regex sweep across the entire repository (`*.py .yml .yaml .json .sh .tf
.md`) found no hardcoded real credentials at baseline or after changes — the only pre-existing weak default was
Grafana's `admin123` password in `docker-compose.yml`, which is now a required environment variable
(`${GRAFANA_ADMIN_PASSWORD:?...}`, documented in `.env.example`) with no default at all, so a misconfigured
deployment fails to start rather than silently running with a known-public password.

## 6. Container Security
- Minimal base image (`python:3.11-slim`); build-only packages are not present in a separate stage but are
  installed and the apt cache is cleaned in the same layer (`rm -rf /var/lib/apt/lists/*`) — a true multi-stage
  build (separate builder/runtime stages) would shave additional size and is listed as a future improvement.
- Non-root user (`appuser`, UID 10001) — already correct at baseline, preserved.
- `HEALTHCHECK` — added in this engagement.
- No secrets baked into the image (only `COPY app/ /app` — no `.env`, no credentials file).
- Vulnerability scanning: Trivy, in CI (`Container Scan` stage). **Not independently re-verified in this
  engagement** — no Docker daemon was available in the sandbox used, so this stage is reviewed by hand for
  correctness rather than executed; see `docs/BASELINE.md`.
- Image signing: **not implemented**. Recommended follow-up: cosign, once images are actually published to a
  registry by CI.
- Immutable tags: Kubernetes/Helm currently reference a mutable tag (`v1.0`). checkov correctly flags this
  (`CKV_K8S_43`, "image should use digest"). **Not fixed in this engagement** because fixing it correctly means
  referencing a real `sha256:...` digest of an image that CI has actually built and pushed — fabricating a
  digest here would be worse than leaving the gap documented. Recommended follow-up: have the `Container Build`
  Jenkins stage capture and record the digest it pushes, then update the manifests/values to reference it.
- Kubernetes-level container security context — see Section 7.

## 7. Kubernetes / Container Runtime Security
Hardened in this engagement (previously only pod-level `runAsNonRoot`/`runAsUser` existed):
`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` (with explicit `/data` and `/tmp` `emptyDir`
volumes for the app's actual write needs), `capabilities: drop: [ALL]`, `seccompProfile: RuntimeDefault`,
`automountServiceAccountToken: false`, a dedicated `devsecops` namespace instead of `default`, and
`imagePullPolicy: Always`. Verified: `checkov` on `kubernetes/` goes from a mix of passing/failing checks to
93/94 passing; the one remaining (`CKV_K8S_43`, image digest) is the documented gap above. **Never used**:
`privileged: true` — no manifest in this repository sets it, and none should.

## 8. IaC Security
`terraform/` scanned with `checkov`: 48/54 checks pass after this engagement's fixes (S3 public-access block,
versioning, KMS encryption, lifecycle policy, explicit bucket policy; CloudTrail log-file validation,
multi-region, CloudWatch Logs integration; an explicit KMS key policy). The 6 remaining findings are documented,
accepted-scope gaps, not silently unscanned:

| Check | Why not fixed here |
|---|---|
| CKV_AWS_252 — CloudTrail SNS topic | Requires provisioning + subscribing an SNS topic; no notification consumer exists in this exam-scope project |
| CKV2_AWS_62 — S3 event notifications | Same — no consumer (Lambda/SQS) exists to notify |
| CKV_AWS_18 — S3 access logging | Requires a second, separately-secured logging bucket; disproportionate for a single audit-log bucket in an exam project |
| CKV_AWS_144 — S3 cross-region replication | Requires a second region's bucket + replication IAM role; cost/scope disproportionate here |
| CKV2_AWS_57 — Secrets Manager rotation | Requires a rotation Lambda tailored to whatever service consumes the secret; no such consumer is defined yet |
| CKV2_AWS_3 — org-wide GuardDuty | Requires an AWS Organizations management-account context this single-account project does not have; a single-account GuardDuty detector (implemented) still provides real threat detection for this account |

`kubernetes/` is also scanned with checkov (Section 7).

## 9. DAST
`security/zap-runner.sh` runs an OWASP ZAP baseline scan against the deployed app
(`http://devsecops-app:5000`), filters out Low/Informational findings, and fails if anything Medium+ remains.
**Not independently re-run in this engagement** — it requires a running target and Docker networking this
sandbox does not have; the script's logic was reviewed by hand and is unchanged from a working baseline.

## 10. Authentication and Authorization
**Implemented**: `POST /users` requires `X-API-Key` (via `APP_API_KEY`) — added in this engagement; the
application previously had no authentication at all. This is a single shared-secret, demo-appropriate control.

**Not implemented (documented, not fabricated)**: the presentation states GitHub OAuth 2.0 for developer access
and JWT for AI-service requests. GitHub's own OAuth is a platform-level control outside this repository's code
(it governs access to the GitHub repo itself, not something this codebase implements). JWT-based auth for the
`ai-agents/*.py` scripts does not exist — they are CI-invoked scripts with no network-exposed API of their own,
so there is no request to authenticate; if these were ever exposed as a callable service, JWT/OAuth2 would need
to be added at that point. No Kubernetes RBAC manifests exist in this repository — the cluster's own default
RBAC applies.

## 11. Data Security
- **Encryption in transit**: Ingress TLS termination is configured (`ssl-redirect: "true"`); the specific TLS
  version negotiated is a property of the Ingress controller's own configuration, not this repository's code —
  the presentation's "TLS 1.3" claim is a controller-configuration target, not something asserted as
  implemented here.
- **Encryption at rest**: the Terraform-managed AWS resources (CloudTrail's S3 bucket, the Secrets Manager
  secret) are encrypted with a customer-managed KMS key (added/tightened in this engagement). The application's
  own SQLite file is not encrypted at rest — acceptable for a demo containing no real user data, documented as
  a gap for any real deployment.
- **Sensitive data handling**: the app never logs request bodies or the API key (Section "Application Logging"
  in `docs/TRD.md`). The sample data model (username, email) is the only "PII-adjacent" data the app handles,
  and it is only ever data a user submits themselves via `POST /users`.
- **Data retention**: the Terraform CloudTrail log bucket has a 365-day expiration + 90-day noncurrent-version
  expiration lifecycle policy (added in this engagement). The application itself defines no retention/deletion
  policy for the `users` table — a real deployment handling actual personal data would need one for GDPR
  purposes; documented as a gap, not implemented (no real personal data flows through this demo app today).

## 12. LLM Security
This section is the one the master engagement instructions specifically call out as critical.

- **Prompt injection**: `code_reviewer.py` sends raw file contents into a prompt template with no sanitization.
  Today this is low-risk because it only ever points at this repository's own small, trusted `app/app.py`. If
  this pattern is ever reused to review externally-supplied or user-uploaded code, it becomes a real
  prompt-injection surface (a crafted comment could attempt to redirect the model's output). Mitigation added in
  this engagement: a hard 20,000-character cap on the code sent into the prompt (defense-in-depth against
  oversized/adversarial input); full sanitization (e.g., stripping comments, structured output enforcement) is
  recommended before ever pointing this at untrusted input.
- **Malicious prompts / model abuse**: the AI scripts are CI-invoked, not exposed as a public API — there is no
  external actor who can submit arbitrary prompts to them today. If they were ever wrapped in a service, rate
  limiting and authentication (Section 10) would need to move to that layer.
- **Sensitive data leakage via prompts/outputs**: reports are written to `reports/*.json` / `docs/*.md` and
  archived as Jenkins artifacts. No secrets or real PII flow through these scripts today (they process this
  repo's own source code and its own Bandit findings). Guidance added in `ai-agents/*.py` docstrings: never
  point these scripts at files containing real credentials or personal data.
- **Unsafe model output consumed downstream**: by design, no AI output is auto-applied to code or
  auto-merged — every report is written for human/CI review. This human-in-the-loop design was already correct
  at baseline and is explicitly preserved and documented here so it is not accidentally automated later without
  someone re-reading this section.
- **Model supply-chain risk**: at baseline, `ai-agents/*.py` ran `os.system("pip install <package> -q")` at
  pipeline runtime with no version pin whenever an import failed — installing whatever was "latest" on PyPI at
  that exact moment, with no integrity verification, and silently executing that new code in the pipeline. This
  is a genuine supply-chain risk and is **fixed** in this engagement: `ai-agents/requirements.txt` pins every
  AI/LLM dependency; the scripts no longer install anything at runtime, they only import and fall back to their
  static report if a package is missing.
- **Malicious model artifacts**: `hf_code_analyzer.py` downloads `distilbert-base-uncased-finetuned-sst-2-english`
  from the Hugging Face Hub. At baseline this used the mutable `main` reference implicitly. **Fixed**: the
  script now accepts `HF_MODEL_REVISION` to pin an exact commit hash, and prints an explicit warning if it falls
  back to `main` (a moving target) — this repository does not fabricate a specific hash it could not verify
  against the live Hub (no Hub network access in the sandbox used for this engagement), but the mechanism to pin
  one is now in place and documented, and defaulting to a warned "main" is safer than silently trusting a
  mutable reference with no warning at all.
- **Dependency vulnerabilities in the AI stack**: `ai-agents/requirements.txt` (Section above) is scanned by the
  same Snyk/Dependency-Check/security-gate pipeline as `app/requirements.txt` — closing a gap where these
  dependencies previously weren't pinned or scannable at all.
- **Input validation (of what reaches the LLM)**: the 20,000-character cap above; `hf_code_analyzer.py` already
  truncates each Bandit finding's text to 512 characters before classification (pre-existing, correct, kept).
- **Output validation**: none of the three scripts parse/execute the model's output as code — all output is
  treated as report text. This is a safe default and is documented as intentional.
- **Rate limiting**: not applicable today (CI-invoked scripts, no exposed endpoint); would be needed if these
  were ever exposed as a service (Section 10).
- **Authentication for LLM APIs**: not applicable today for the same reason.
- **Logging without leaking sensitive prompts/data**: reports contain code/findings from this repo's own
  source, not secrets. If these scripts are ever pointed at real user data, the reports (which are archived
  Jenkins artifacts) would need redaction — documented as a requirement for that future use case.
- **A specific, honestly-documented model-choice limitation**: `distilbert-base-uncased-finetuned-sst-2-english`
  is a sentiment classifier (positive/negative movie-review-style text), not a security classifier. Using its
  confidence score as a security "priority" signal is a semantic mismatch with what the model was trained to
  do. It produces a number that looks meaningful but isn't grounded in security severity. This is preserved per
  the instruction not to replace working functionality, and is called out here, in `docs/GAP_ANALYSIS.md`, and
  in `docs/TRD.md` so nobody mistakes it for a validated severity model. Recommended replacement: a model
  fine-tuned for vulnerability/CWE classification, or an LLM prompted specifically for severity triage with a
  structured (not sentiment) output schema.

## 13. Threat Model
| Threat | Attack Vector | Risk | Mitigation |
|---|---|---|---|
| SQL injection | Malicious input to `/users` or `/search` | Was Medium (unvalidated concat risk if ever introduced) | Parameterized queries everywhere (verified: 0 Semgrep findings for the custom SQLi rule) |
| Unauthorized data write | Anonymous `POST /users` | High (was: no auth at all) | API-key gate (`APP_API_KEY`), documented as demo-grade |
| Denial of service via request flooding | Repeated `POST /users`/`/search` | Medium | In-process rate limiter (documented single-instance limitation) |
| Secret leaked into git history | Accidental commit of a real credential | High if it occurred | gitleaks CI stage + `.gitignore` on `.env` |
| Vulnerable dependency shipped | Outdated/CVE-affected package in `requirements.txt` | High | Snyk + OWASP Dependency-Check, both pinned and scanned files |
| Vulnerable/misconfigured container image | Base image or added packages | High | Trivy scan; minimal slim base; non-root |
| Privilege escalation from a compromised pod | Container breakout attempt | High | `allowPrivilegeEscalation: false`, capabilities dropped, seccomp, non-root, read-only rootfs |
| Lateral movement from a compromised pod | Pod-to-pod network access | Medium-High | Zero-trust NetworkPolicy (deny-all implicit, explicit allows only) |
| Misconfigured Kubernetes manifest reaching prod | Missing resource limits / root container / `:latest` tag | High | OPA admission policy (`security/policy.rego`) + checkov IaC scan |
| Supply-chain compromise via unpinned CI-installed packages | AI scripts pulling "latest" from PyPI at runtime | Medium-High (was present, now fixed) | `ai-agents/requirements.txt`, no runtime installs |
| Mutable ML model reference silently changing behavior | HF Hub `main` branch updated upstream | Medium | `HF_MODEL_REVISION` pinning mechanism + explicit warning when unpinned |
| Prompt injection via reviewed source | Adversarial comments in code sent to an LLM | Low today, Medium if reused on untrusted input | Size cap; human-in-the-loop report review; documented caution for future untrusted-input use |
| Weak default credential | Grafana `admin123` | Medium (local-only exposure, but a known public default) | Required env var with no default, `.env.example` guidance |

## 14. Compliance Alignment (ISO/IEC 42001, NIST AI RMF, GDPR)
This project supports alignment with these frameworks — it does not claim certification against any of them:
- **ISO/IEC 42001 (AI management systems)**: every AI run is versioned and auditable via MLflow (model,
  duration, findings); AI-generated output never auto-merges (human-in-the-loop, Section 12); this SECURITY.md
  documents known AI-specific risks and their mitigations/limitations.
- **NIST AI RMF**: risk identification for the LLM components is documented in Section 12; monitoring exists via
  MLflow (AI-specific) and Prometheus/Grafana/Loki (system-level).
- **GDPR**: the sample application collects only data a user submits themselves (username/email); no special
  categories of data are processed; a data-retention policy exists at the infrastructure level (CloudTrail logs,
  Section 11) but not yet at the application data level (the `users` table has no retention/deletion job) —
  documented as a gap for any deployment handling real personal data, not fabricated as solved.

Formal certification against any of these would additionally require (not present here, and not claimed):
a data inventory/register, a Data Protection Officer sign-off, a completed Data Protection Impact Assessment,
and a formal third-party audit.
