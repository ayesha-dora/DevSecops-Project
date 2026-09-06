# Implementation Plan

This plan turns `docs/GAP_ANALYSIS.md` into ordered, verifiable work. Every phase ends with a test/verification
step, and every phase's outcome is recorded in `CONTEXT.md`'s change log as it's completed — not batched at the
end. Phases are scoped to what a single engineer can actually verify without a live Kubernetes cluster, live AWS
account, or live Jenkins server (none of which this environment has) — those items are flagged **[external]** and
their plan is "provide correct, reviewed configuration; verification requires the target environment."

## Phase 1 — Repository Stabilization
- Fix `pytest-cov==4.1.1` → `4.1.0` in `app/requirements.txt`.
- Confirm `pip install -r app/requirements.txt` succeeds clean.
- Verify: `pip install` exit 0; `python3 -m py_compile` on all `.py` files.

## Phase 2 — Application
- Implement `/search` endpoint (parameterized `LIKE` query against `username`/`email`, `q` length-capped and
  charset-checked) so the existing test passes.
- Add a lightweight API-key check (`X-API-Key` header vs. `APP_API_KEY` env var) on `POST /users` — the only
  mutating route.
- Add input validation: max lengths on `username`/`email`, a simple email-shape check.
- Add a basic in-process rate limiter (token bucket per client IP) on `POST /users` and `/search`, documented as
  a single-instance mitigation (not a substitute for an API gateway / Ingress-level limiter at real scale).
- Add structured logging (method, path, status, latency; no request bodies, no secrets) via Python's `logging`
  module to stdout, so Promtail (Phase 8) can ship it.
- Verify: `pytest tests/ -v` — all tests green, including a new test for `/search` behavior and for the
  API-key-gated path.

## Phase 3 — LLM / AI Agents
- Do **not** replace Ollama/LangChain/Hugging Face/LlamaIndex/MLflow usage — verify each script's fallback path
  runs cleanly with no network/model available (this sandbox has neither Ollama nor internet access to the HF
  Hub with a real model download budget).
- Add `ai-agents/requirements.txt` pinning `transformers`, `torch` (CPU wheel), `langchain`,
  `langchain-community`, `llama-index` + its Ollama/HuggingFace extras, and `mlflow`, replacing the runtime
  `os.system("pip install ...")` calls with a documented `pip install -r ai-agents/requirements.txt` step run
  once in CI, before the AI stages — so behavior is reproducible and no stage silently reaches out to PyPI for
  "latest."
- Pin the Hugging Face model reference in `hf_code_analyzer.py` to a specific `revision` instead of a mutable
  tag.
- Add a bounded size guard before sending `app/app.py`'s contents into the LangChain prompt (defense-in-depth
  against oversized/adversarial input, without changing normal behavior for this repo's own small file).
- Verify: run `code_reviewer.py`, `hf_code_analyzer.py`, `code_indexer.py`, `mlflow_logger.py` locally with
  Ollama/HF/MLflow unavailable; confirm each produces its documented fallback report/file without raising, and
  that MLflow logging skips missing reports gracefully (already implemented) rather than crashing.

## Phase 4 — Containerization
- Add a `HEALTHCHECK` instruction to `app/Dockerfile` hitting `/health`.
- Keep the existing non-root user, slim base image, and gunicorn entrypoint (already correct — no change).
- Verify: manual Dockerfile review (`hadolint`-style checklist) since no Docker daemon is available in this
  sandbox; full `docker build` + container run is flagged **[external]** for verification on the user's own
  machine/CI agent, and the exact commands to do so are given in `CONTEXT.md`.

## Phase 5 — CI/CD (Jenkinsfile)
Rebuild the stage list to match what the repository actually contains, in the dependency order the requirements
document expects:

```
Checkout
 → Install Dependencies (pip install app + ai-agents requirements)
 → Lint (flake8)
 → Unit Tests (pytest, JUnit + coverage XML output)
 → SAST (Bandit + Semgrep)
 → SonarQube Analysis (sonar-scanner, reads bandit + coverage reports)
 → Secret Scan (gitleaks)
 → Dependency Scan / SCA (Snyk + OWASP Dependency-Check)
 → AI Code Review & Vulnerability Analysis & Doc Gen (code_reviewer, hf_code_analyzer, code_indexer)
 → MLflow Logging (after all three AI reports exist)
 → Container Build
 → Container Scan (Trivy)
 → IaC Scan (tfsec/checkov on terraform/ and kubernetes/)
 → OPA Compliance Gate
 → Security Gate (aggregate all scan results; enforce when ENFORCE_SECURITY=true)
 → Deploy to Kubernetes
 → DAST (OWASP ZAP)
 → Post-Deployment Verification (health check smoke test)
```
- Keep the existing `ENFORCE_SECURITY` parameter and non-blocking (`|| true`) default philosophy — documented
  explicitly, not silently changed — but centralize the pass/fail decision in one new "Security Gate" stage
  instead of scattering ad-hoc `if` blocks per tool.
- Verify: review each stage's shell for correctness; **[external]** full pipeline execution requires a real
  Jenkins agent with these tools/images available, which this sandbox cannot provide — the Jenkinsfile is
  reviewed line-by-line, and the underlying scripts it calls (pytest, bandit, semgrep, the AI scripts) are each
  executed directly in this sandbox as a proxy for stage correctness.

## Phase 6 — Infrastructure
- No structural Terraform changes (existing resources are correct and minimal); add a `variables.tf` making the
  region configurable instead of hardcoded in two places, and expand comments documenting the explicit scope
  boundary (governance/secrets only, cluster assumed to pre-exist).
- Verify: `terraform validate` requires the `hashicorp/aws` provider plugin download — attempted in this sandbox
  if network egress allows; otherwise flagged **[external]**, with the HCL reviewed manually for syntax
  correctness.

## Phase 7 — Security
- gitleaks config + `.gitleaks.toml` and a Jenkins stage.
- `.env.example` at repo root enumerating every environment variable used anywhere in the repo (app, AI agents,
  docker-compose), with placeholder values and comments — never real values.
- Move the Grafana default admin password out of `docker-compose.yml` into an env var.
- Verify: manual secret-pattern re-sweep after all changes; confirm `.env.example` contains no real secret by
  construction (only placeholders).

## Phase 8 — Observability
- Add a Promtail service + config to `docker-compose.yml` and `monitoring/` so container logs actually reach
  Loki, making the Grafana "Application Security Logs" panel meaningful.
- Verify: review Promtail scrape config against the Loki push API contract; full end-to-end log flow is
  **[external]** (requires `docker compose up`, which needs a Docker daemon this sandbox does not have).

## Phase 9 — Testing
- Extend `app/tests/test_app.py` with tests for `/search` (valid query, empty query, oversized query) and for
  the API-key gate on `POST /users` (missing key → 401, wrong key → 403, correct key → 201).
- Verify: `pytest tests/ -v --cov=. --cov-report=term-missing` — all green, and note the resulting coverage
  percentage honestly in `CONTEXT.md` (do not claim 100% if it isn't).

## Phase 10 — Documentation
- `docs/PRD.md`, `docs/TRD.md`, `docs/SECURITY.md`, `docs/FLOW.md`, `docs/ARCHITECTURE.md` (this plan's sibling
  documents), each reflecting the *implemented* state, with explicit "Planned / requires external infrastructure"
  labels for anything not actually running.
- Correct `README.md` (remove the non-existent `chaos/` reference; add the new stages/tools to the feature list;
  add `.env.example` usage instructions).
- `CONTEXT.md` at repo root, updated after every phase above, not just at the end.
- `docs/FINAL_AUDIT.md` written last, after Phase 9's test run.

## Verification Gate Before Calling Anything "Done"
No phase is marked complete in `CONTEXT.md` until either (a) it was executed in this sandbox with output captured
(pytest, bandit, semgrep, py_compile, yamllint), or (b) it is explicitly labeled **[external]** with the exact
command a human should run on a machine that has the missing dependency (Docker daemon, Kubernetes cluster,
Jenkins agent, AWS credentials), and that label is carried through into `docs/FINAL_AUDIT.md` unchanged. This is
the mechanism that prevents this engagement from claiming untested functionality works.
