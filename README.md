# DevSecOps-CI-CD-Project

[![CI](https://img.shields.io/badge/ci-jenkins-blue)](https://www.jenkins.io/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-blueviolet)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/helm-chart-lightgrey)](https://helm.sh/)
[![Security](https://img.shields.io/badge/security-multi--tool-red)](#security--compliance)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

AAI-Augmented DevSecOps CI/CD pipeline for building, testing, securing, and deploying a Python web application to Kubernetes. This repository demonstrates a security-first, AI-assisted pipeline integrating traditional SAST/DAST/container scanning with LLM-based code review and ML experiment tracking.

---

## Table of Contents

- Project Title & Overview
- Architecture & Pipeline Flow
- Repository Directory Structure
- Key Features & Tools
- Setup & Execution Guide
- Quick Developer Commands
- Kubernetes & Helm
- Security & Compliance Gate Examples
- Observability & Resiliency
- Regulatory Alignment & Governance
- Contributing & Support

---

## Project Title & Overview

**DevSecOps-CI-CD-Project** — an AI-augmented, security-first CI/CD pipeline for Python applications.

Purpose:
- Automate secure build/test/deploy workflows with Jenkins.
- Use SAST, dependency scanning, container scanning, and DAST to identify vulnerabilities early.
- Integrate LLM-driven code review and MLflow tracking for AI-driven insights and auditability.
- Enforce runtime security and compliance using OPA admission policies.
- Deploy to Kubernetes and provide observability (Prometheus / Grafana / Loki).
- Provide infrastructure-as-code with Terraform targeting AWS ap-south-1 (Mumbai).

Core technologies: Jenkins, Kubernetes, Docker, Python, LangChain/HuggingFace, MLflow, Helm, Terraform, Snyk, Trivy, Bandit, Semgrep, OWASP ZAP, OPA, Prometheus, Grafana, Loki, LitmusChaos.

---

## Architecture & Pipeline Flow

High-level flow (commit → secure deployment):

1. Developer pushes code to Git (PR created).
2. Jenkins pipeline (Jenkinsfile) runs multi-stage CI:
   - Checkout Code
   - SAST: Bandit & Semgrep
   - Dependency Scanning: Snyk & OWASP Dependency-Check
   - AI Code Review (LLM) & MLflow Logging
   - Container Build & Container Scan (Trivy)
   - OPA Compliance Gate (policy.rego test harness)
   - Deploy to Kubernetes (Helm or kubectl)
   - Dynamic Security Scan (OWASP ZAP) against running app
3. Reports/artifacts archived (reports/*) and optionally published to dashboards and MLflow.
4. Prometheus scrapes the application and Jenkins; Promtail ships container logs (including the app's) to Loki; Grafana dashboard visualizes metrics and logs.
5. Chaos engineering (LitmusChaos) is **not implemented** in this repository — it was referenced here in an earlier version as a placeholder that never existed on disk. Documented in `docs/GAP_ANALYSIS.md` as a future improvement, not claimed as present.

Notes:
- All security scan steps are non-blocking by default (use of `|| true` in pipeline) to ensure artifacts are produced during test runs while keeping the pipeline resilient for CI feedback. An `ENFORCE_SECURITY` pipeline parameter and a single aggregated **Security Gate** stage (`security/security_gate.py`) control enforcement in one place — see `docs/SECURITY.md`.
- OPA policy (`security/policy.rego`) enforces runtime constraints (no root, no `:latest`, resource requests/limits).
- See `CONTEXT.md` and `docs/` for the full documentation set (PRD, TRD, SECURITY, FLOW, ARCHITECTURE, GAP_ANALYSIS, IMPLEMENTATION_PLAN, BASELINE, FINAL_AUDIT) produced alongside a full audit/hardening pass of this repository.

---

## Repository Directory Structure

Visual tree (primary folders and important files):

```
.
├── app/                              # Flask application, tests, pinned requirements.txt, Dockerfile
├── ai-agents/                        # AI/LLM CI-stage scripts + their own pinned requirements.txt
├── helm/
│   └── devsecops-app/                # Helm chart (deployment, service, ingress, networkpolicy)
├── kubernetes/                       # namespace, deployment, service, ingress, network-policy manifests
├── monitoring/                       # Prometheus, Loki, Promtail, Grafana dashboard configs
├── security/
│   ├── snyk-config.json
│   ├── owasp-zap-config.conf
│   ├── zap-runner.sh
│   ├── policy.rego
│   ├── dependency-check.sh
│   ├── gitleaks.toml
│   ├── security_gate.py              # aggregates all scan reports into one pass/fail decision
│   └── examples/                      # example Kubernetes manifests (good & bad)
├── terraform/                         # Terraform IaC (AWS governance/security) for ap-south-1
├── docs/                              # PRD, TRD, SECURITY, FLOW, ARCHITECTURE, GAP_ANALYSIS, etc.
├── CONTEXT.md                         # persistent project memory — read this first
├── .env.example                       # every environment variable used anywhere in this repo
├── Jenkinsfile
├── docker-compose.yml                 # local toolchain, including the app itself
├── README.md
└── reports/                           # Generated test / scan reports (gitignored)
```

There is no `chaos/` directory — an earlier version of this README referenced one as a placeholder for
LitmusChaos experiments that was never actually created. See `docs/GAP_ANALYSIS.md` for this and every other
gap between what was documented and what existed, and what was done about each.

---

## Key Features & Tools

### CI/CD & Automation
- Jenkins-driven pipeline (root `Jenkinsfile`) defines ordered stages:
  - Checkout → Install Dependencies → Lint → Unit Tests → SAST → SonarQube → Secret Scan → Dependency Scan → AI Code Review & Vulnerability Analysis & Doc Gen → MLflow Logging → Container Build → Container Scan → IaC Scan → OPA Compliance Gate → Security Gate → Deploy → DAST (ZAP) → Post-Deployment Verification
- Reports archived for artifact inspection.

### AI & LLMOps
- LangChain + local Ollama (CodeLlama) code review, Hugging Face Transformers vulnerability triage, LlamaIndex + Ollama (Llama3) + HF embeddings documentation generation (`ai-agents/*`).
- Every AI script degrades to a documented static fallback report if its live model/service is unavailable — the pipeline never hard-fails for that reason alone.
- MLflow integration tracks every AI run (`ai-agents/mlflow_logger.py`), with a hard 10s connect timeout so an unreachable MLflow server can't hang the pipeline.
- AI/LLM dependencies are pinned in `ai-agents/requirements.txt` — see `docs/SECURITY.md` "Model Supply Chain" for why this matters and what changed.

### Security & Compliance
- SAST: Bandit (Python) and Semgrep (config at `security/semgrep-rules.yaml`).
- SonarQube: configured via `sonarqube/sonar-project.properties`, run by a dedicated Jenkins stage.
- Secret scanning: gitleaks (`security/gitleaks.toml`).
- Dependency scanning: Snyk (`security/snyk-config.json`) + OWASP Dependency-Check (`security/dependency-check.sh`), covering both `app/requirements.txt` and `ai-agents/requirements.txt`.
- Container scanning: Trivy (Jenkins stage produces `reports/trivy-report.json`).
- IaC scanning: checkov against `terraform/` and `kubernetes/`.
- DAST: OWASP ZAP runner (`security/zap-runner.sh`) with `security/owasp-zap-config.conf`.
- Policy: OPA policy in `security/policy.rego` + test harness `security/test_policy.sh`.
- Security Gate: `security/security_gate.py` aggregates every scan's results into one pass/fail decision, enforced only when `ENFORCE_SECURITY=true`.
- Reports location: `reports/*` and archived by Jenkins post step.
- Full write-up, including the LLM-specific security section and a threat model: `docs/SECURITY.md`.

### Infrastructure & Kubernetes
- Helm chart: `helm/devsecops-app/` (templated Deployment, Service, Ingress, NetworkPolicy) with a hardened container `securityContext` (no privilege escalation, all capabilities dropped, read-only root filesystem, seccomp).
- Kubernetes manifests: `kubernetes/namespace.yaml` (dedicated `devsecops` namespace — apply this first), `deployment.yaml`, `service.yaml`, `ingress.yaml`, `network-policy.yaml`.
- Terraform: AWS governance/security IaC (KMS, CloudTrail, GuardDuty, Security Hub, Secrets Manager, an IAM role) in `terraform/` — assumes an existing Kubernetes cluster; see `docs/TRD.md` for this scope boundary.

### Observability & Resiliency
- Prometheus config: `monitoring/prometheus.yml` — scrapes the app and Jenkins.
- Loki + Promtail: `monitoring/loki-config.yaml` + `monitoring/promtail-config.yaml` — Promtail actually ships container logs (including the app's) to Loki; both run as services in `docker-compose.yml`.
- Grafana dashboard: `monitoring/grafana-dashboard.json` — prebuilt dashboard with HTTP Requests Rate and Application Security Logs (now actually populated).
- Chaos engineering is not implemented — see the Repository Directory Structure note above.

---

## Setup & Execution Guide

Below are pragmatic steps to run locally, run scans, and deploy.

Prerequisites
- Docker
- kubectl (configured to your cluster)
- helm
- Jenkins (or use GitHub Actions / your CI)
- Python 3.8+
- (Optional) Docker access on Jenkins agent to run scanners in containers
- (Optional) Snyk token in env: `SNYK_TOKEN`

1) Clone
```bash
git clone https://github.com/<your-org>/DevSecOps-CI-CD-Project.git
cd DevSecOps-CI-CD-Project
cp .env.example .env   # then fill in real values — see .env.example for what each variable does
```

2) Install dependencies and run local tests & SAST (developer machine)
```bash
pip install -r app/requirements.txt
pip install -r ai-agents/requirements.txt   # optional — only needed for the live (non-fallback) AI/LLM paths

# Unit tests + coverage
cd app
pytest tests/ -v --cov=. --cov-report=term-missing --junitxml=../reports/test-results.xml
cd ..

# Bandit & Semgrep
bandit -r app -f json -o reports/bandit-report.json --severity-level medium || true
semgrep --config security/semgrep-rules.yaml app --json --output reports/semgrep-report.json || true

# Secret scan
gitleaks detect --source=. --config=security/gitleaks.toml --no-git || true

# IaC scan
checkov -d terraform --compact
checkov -d kubernetes --framework kubernetes --compact
```

3) Run dependency scans
```bash
# Snyk (requires SNYK_TOKEN if scanning private data)
snyk test --severity-threshold=high --file=app/requirements.txt --json > reports/snyk-report.json || true

# OWASP Dependency-Check (script provided)
chmod +x security/dependency-check.sh
./security/dependency-check.sh
# HTML output: reports/dependency-check-report.html
```

4) Run OPA policy checks (test harness)
```bash
chmod +x security/test_policy.sh
./security/test_policy.sh
```

5) Run ZAP DAST (containerized runner)
```bash
chmod +x security/zap-runner.sh
./security/zap-runner.sh
# outputs: reports/zap-report.json, reports/zap-report-filtered.json
```

6) Build image & run Trivy scan
```bash
# Build Docker image — build context MUST be the repo root (not ./app), because app/Dockerfile's COPY
# instructions are written relative to the repo root (COPY app/requirements.txt, COPY app/ /app). An earlier
# version of this README suggested `docker build ... ./app`, which does not match the Dockerfile and fails.
docker build -t ayeshaakram786/devsecops-app:local -f app/Dockerfile .

# Trivy (containerized)
docker run --rm -v trivy-cache:/root/.cache/trivy aquasec/trivy:latest image --format json --severity HIGH,CRITICAL ayeshaakram786/devsecops-app:local > reports/trivy-report.json || true
```

7) Deploy infrastructure (Terraform) — example (edit variables)
```bash
cd terraform
terraform init
terraform plan -var="aws_region=ap-south-1"
terraform apply -var="aws_region=ap-south-1"
```

8) Deploy to Kubernetes (Helm)
```bash
# render
helm template devsecops-app ./helm/devsecops-app

# install to cluster (ensure TLS secret exists or set ingress.enabled=false)
helm install devsecops-app ./helm/devsecops-app --namespace devsecops --create-namespace

# Or apply plain manifests directly (apply the namespace first)
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/network-policy.yaml
kubectl apply -f kubernetes/ingress.yaml
```

9) Validate monitoring / dashboards
- Prometheus targets: Ensure `monitoring/prometheus.yml` is loaded into your Prometheus and view `http://<prometheus>:9090/targets`.
- Import `monitoring/grafana-dashboard.json` into Grafana (UI: Dashboards → Import).

10) Trigger full Jenkins pipeline
- Push branch / open PR. Jenkinsfile is in root and contains stages in the requested order. Ensure Jenkins agents have required tools or allow runner containers.

---

## Quick Developer Commands

Run OPA tests:
```bash
chmod +x security/test_policy.sh
./security/test_policy.sh
```

Generate dependency-check report:
```bash
chmod +x security/dependency-check.sh
./security/dependency-check.sh
# open reports/dependency-check-report.html
```

Render helm templates:
```bash
helm template devsecops-app ./helm/devsecops-app
```

Open PR (browser):
```
https://github.com/<your-org>/DevSecOps-CI-CD-Project/compare/feature/add-security-configs?expand=1
```

---

## Security & Compliance Gate Examples

- OPA policy: `security/policy.rego` — denies pods/containers that:
  - run as root (enforces `runAsNonRoot: true` / `runAsUser`),
  - use `:latest` tag or omit tag,
  - do not declare resource requests and limits.

- Snyk / Trivy / Dependency-Check / Bandit / Semgrep produce machine-readable reports in `reports/` for artifact storage and auditability.

- DAST: `security/zap-runner.sh` runs OWASP ZAP baseline and filters low/informational findings. The pipeline archives ZAP results and can be configured to fail on MEDIUM+ findings.

---

## Observability & Resiliency

- Prometheus scrape config: `monitoring/prometheus.yml` — scrapes `devsecops-app:5000` and Jenkins.
- Loki config: `monitoring/loki-config.yaml` — single-binary config with 168h retention.
- Grafana dashboard: `monitoring/grafana-dashboard.json` — ready-to-import dashboard with:
  - HTTP Requests Rate (Prometheus)
  - Application Security Logs (Loki)
- Chaos experiments: consider adding LitmusChaos manifests to `chaos/` to validate resilience and rollback capabilities.

---

## Regulatory Alignment & Governance

This project is structured to help meet industry governance and AI safety requirements:
- ISO/IEC 42001 — AI governance and risk management alignment through documented LLM review steps, MLflow audit trails, and reproducible pipelines.
- NIST AI Risk Management Framework (AI RMF) — leverages monitoring, logging, model governance, and explainability via the ai-agents and MLflow tracking.
- GDPR — personal data handling must be evaluated for dataset and telemetry ingestion; logs should be redacted as required. The repo provides secure scanning and policy gates to reduce risk surface.

Additions needed for formal certification:
- Data inventories, DPO sign-offs, documented retention & deletion policies, and formal threat modelling documentation.

---

## Contributing

Contributions are welcome — please follow these guidelines:
- Open a branch `feature/<your-change>` and create a PR.
- Include tests and update docs.
- For infra changes, provide terraform plan output and a rollback plan.

Suggested PR reviewers: security, infra, and platform owners. Add labels like `security`, `infra`, `certification` as needed.

---

## Troubleshooting & Tips

- If probes fail after deploying with `runAsUser`, ensure image filesystem permissions allow non-root access (UID 10001 ownership).
- Agents may need Docker-in-Docker privileges for scanner containers; alternatively configure docker socket or use remote runners.
- For local TLS testing, map `devsecops.local` to ingress IP in `/etc/hosts`.

---

