# Architecture

## 1. High-Level Architecture

```mermaid
flowchart TB
    subgraph DEV["Development"]
        DEVELOPER[Developer] --> GITREPO[Git Repository]
    end

    subgraph CI["CI/CD - Jenkins"]
        GITREPO -->|webhook| PIPE[Jenkins Pipeline]
        PIPE --> QUALITY[Lint + Unit Tests + SonarQube]
        PIPE --> SECURITY[SAST + SCA + Secret Scan + IaC Scan]
        PIPE --> AI[AI/LLM Agents: code review, HF vuln triage, LlamaIndex docs]
        PIPE --> BUILDSTEP[Container Build + Trivy Scan]
        AI --> MLFLOWSVC[MLflow Tracking Server]
    end

    subgraph POLICY["Policy"]
        BUILDSTEP --> OPAGATE[OPA Compliance Gate]
        SECURITY --> GATE[Security Gate - aggregated]
        OPAGATE --> GATE
    end

    subgraph RUNTIME["Kubernetes Cluster - devsecops namespace"]
        GATE -->|deploy| K8SDEPLOY[Deployment: 2 replicas]
        K8SDEPLOY --> K8SSVC[Service]
        K8SSVC --> ING[Nginx Ingress - TLS termination]
        NETPOL[NetworkPolicy - zero trust] -.restricts.-> K8SDEPLOY
    end

    subgraph OBS["Observability"]
        K8SDEPLOY -->|/metrics| PROM[Prometheus]
        K8SDEPLOY -->|stdout logs| PROMTAIL[Promtail]
        PROMTAIL --> LOKI[Loki]
        PROM --> GRAFANA[Grafana]
        LOKI --> GRAFANA
    end

    subgraph DAST_STAGE["Post-Deploy Security"]
        ING --> ZAP[OWASP ZAP DAST]
    end

    subgraph CLOUD["AWS (Terraform-managed governance)"]
        KMS[KMS Key] --> S3TRAIL[CloudTrail S3 Bucket - encrypted, versioned]
        CLOUDTRAIL[CloudTrail - multi-region] --> S3TRAIL
        CLOUDTRAIL --> CWLOGS[CloudWatch Logs]
        GUARDDUTY[GuardDuty]
        SECHUB[Security Hub]
        SECRETSMGR[Secrets Manager - KMS encrypted]
        IAMROLE[IAM Role - Jenkins]
    end

    K8SDEPLOY -.assumed pre-existing cluster, not provisioned by this Terraform.-> CLOUD
```

**Trust boundaries**: the Jenkins pipeline is trusted to run scanners and deploy (it holds no application
secrets beyond what CI tooling itself needs — Snyk/SonarQube tokens, documented in `.env.example`); the
Kubernetes cluster boundary is enforced by NetworkPolicy (only Ingress-controller and monitoring namespaces may
reach the app pod) and by the container securityContext (no privilege escalation, no capabilities, read-only
root filesystem); the AWS account boundary is governed by the Terraform-managed IAM role, KMS key, and
GuardDuty/Security Hub visibility — Terraform does not manage the Kubernetes cluster's own trust boundary
(RBAC), which is an explicitly documented gap (see `docs/SECURITY.md` Section 10).

## 2. Component Architecture

```mermaid
flowchart LR
    subgraph APP["app/"]
        FLASK[app.py - Flask REST API]
        TESTS[tests/test_app.py]
    end
    subgraph AGENTS["ai-agents/"]
        CR[code_reviewer.py]
        HFA[hf_code_analyzer.py]
        CI2[code_indexer.py]
        MLF[mlflow_logger.py]
    end
    subgraph SEC["security/"]
        BANDITCFG[bandit.yaml]
        SEMGREPCFG[semgrep-rules.yaml]
        SNYKCFG[snyk-config.json]
        TRIVYCFG[trivy.yaml]
        GITLEAKSCFG[gitleaks.toml]
        REGO[policy.rego]
        GATE2[security_gate.py]
    end
    subgraph INFRA["kubernetes/ + helm/ + terraform/"]
        K8SMANIFESTS[Plain manifests]
        HELMCHART[Helm chart]
        TF[Terraform AWS governance]
    end
    subgraph MON["monitoring/"]
        PROMCFG[prometheus.yml]
        LOKICFG[loki-config.yaml]
        PROMTAILCFG[promtail-config.yaml]
        GRAFDASH[grafana-dashboard.json]
    end

    FLASK --> TESTS
    CR --> MLF
    HFA --> MLF
    CI2 --> MLF
    GATE2 -.reads reports produced by.-> BANDITCFG
    GATE2 -.reads reports produced by.-> SNYKCFG
    GATE2 -.reads reports produced by.-> TRIVYCFG
    GATE2 -.reads reports produced by.-> GITLEAKSCFG
    K8SMANIFESTS -.equivalent to.-> HELMCHART
    PROMTAILCFG --> LOKICFG
```

## 3. Application Architecture
See `docs/TRD.md` Section 4. Single Flask process, gunicorn-served, SQLite-backed, stateless except for that
SQLite file.

## 4. CI/CD Architecture
See `docs/TRD.md` Section 11 and `docs/FLOW.md` "CI/CD Flow" for the full stage diagram.

## 5. Security Architecture
See `docs/SECURITY.md` in full.

## 6. Cloud Architecture
Terraform manages AWS-account-level governance (KMS, CloudTrail, GuardDuty, Security Hub, Secrets Manager, an
IAM role) around an assumed pre-existing Kubernetes cluster — see the High-Level Architecture diagram above,
"CLOUD" subgraph, and its dashed relationship to the Kubernetes runtime. This is a deliberate scope boundary
(documented in `docs/GAP_ANALYSIS.md` "Architecture Problems"), not a missing piece silently glossed over.

## 7. LLM Architecture
See `docs/TRD.md` Sections 7–9 and `docs/FLOW.md` "LLM Flow" for the full diagram: three independent,
CI-invoked scripts (code review, vulnerability triage, documentation generation), each with a live path (local
Ollama / Hugging Face Hub) and a static fallback path, all logged to MLflow.

## 8. Deployment Architecture
See `docs/FLOW.md` "Deployment Flow": a built and Trivy-scanned image is deployed either via plain `kubectl
apply` of `kubernetes/*.yaml` or via the equivalent Helm chart, into a dedicated `devsecops` namespace, with
2 replicas behind a ClusterIP Service and an Nginx Ingress doing TLS termination.

## 9. Data Flow
See `docs/FLOW.md` "Application Flow" and "LLM Flow" for request-level and AI-pipeline-level data flow
respectively. At a system level: source code and configuration flow from the developer through Git into
Jenkins; Jenkins produces scan reports (security data) and AI reports (AI-generated outputs) as
`reports/*.json`/`docs/*.md` artifacts; the built container image flows from Jenkins to the Kubernetes cluster;
application logs and metrics flow from running pods to Promtail/Loki and Prometheus respectively, and from
there to Grafana for a human to view.

## 10. Trust Boundaries
Covered inline under "High-Level Architecture" above. The three boundaries that matter most for this project's
threat model (see `docs/SECURITY.md` Section 13) are: (a) anonymous internet → Ingress (TLS termination, no
authentication at the Ingress layer itself — authentication happens at the application layer for writes), (b)
Ingress → application pod (NetworkPolicy-restricted), (c) CI pipeline → AWS/Kubernetes (governed by the
Terraform-managed IAM role and whatever kubeconfig/credentials the real Jenkins agent is given — this
repository does not itself store cluster credentials).

## 11. External Dependencies
Ollama (local, for `code_reviewer.py`/`code_indexer.py`'s live path), the Hugging Face Hub (model downloads,
pinned via `HF_MODEL_REVISION` where set), an MLflow tracking server, a SonarQube server, Snyk's API, a
container registry (referenced as `ayeshaakram786/devsecops-app` — update to your own registry before any real
deployment), an Nginx Ingress controller, and — for the Terraform stack — the AWS API. None of these are
bundled with this repository; `docker-compose.yml` stands up local instances of most of them (SonarQube,
Prometheus, Grafana, MLflow, ZAP, Loki+Promtail, and now the app itself) for local development.
