# System Flow

Diagrams reflect the actual implemented flow in this repository, not the aspirational version from the
presentation slides — see `docs/SECURITY.md` for exactly where those diverge (TLS 1.3 / OAuth2 / JWT / mTLS).

## User Flow

```mermaid
flowchart LR
    U[User / Client] -->|HTTPS via Ingress TLS termination| ING[Nginx Ingress]
    ING --> SVC[Kubernetes Service]
    SVC --> POD1[devsecops-app pod 1]
    SVC --> POD2[devsecops-app pod 2]
    POD1 -->|GET /| INFO[App info JSON]
    POD1 -->|GET /health| HEALTH[Liveness/Readiness probe target]
    POD1 -->|GET /users, POST /users| USERS[SQLite users table]
    POD1 -->|X-API-Key required on POST| AUTH{API key valid?}
    AUTH -->|no| ERR401[401/403 JSON error]
    AUTH -->|yes| USERS
    POD1 -->|GET /search?q=| SEARCH[Parameterized LIKE query]
    POD1 -->|GET /metrics| PROM[Prometheus exposition]
```

## Application Flow (request handling)

```mermaid
flowchart TD
    REQ[Incoming request] --> LOG1[before_request: start timer]
    LOG1 --> ROUTE{Route}
    ROUTE -->|POST /users| RL1{Rate limit ok?}
    RL1 -->|no| R429[429 rate limited]
    RL1 -->|yes| AUTHCHK{APP_API_KEY set?}
    AUTHCHK -->|yes, header missing| R401[401]
    AUTHCHK -->|yes, header wrong| R403[403]
    AUTHCHK -->|no or valid key| VALIDATE1{Input valid length/shape?}
    VALIDATE1 -->|no| R400[400]
    VALIDATE1 -->|yes| INSERT[Parameterized INSERT]
    INSERT --> R201[201 created]

    ROUTE -->|GET /search| RL2{Rate limit ok?}
    RL2 -->|no| R429b[429]
    RL2 -->|yes| VALIDATE2{Query length ok?}
    VALIDATE2 -->|no| R400b[400]
    VALIDATE2 -->|yes| LIKEQ[Parameterized LIKE query]
    LIKEQ --> R200[200 with results]

    R201 --> LOG2[after_request: log method/path/status/duration]
    R400 --> LOG2
    R401 --> LOG2
    R403 --> LOG2
    R429 --> LOG2
    R200 --> LOG2
    LOG2 --> RESP[Response returned]
```

## LLM Flow

```mermaid
flowchart TD
    JENKINS[Jenkins: AI stage triggered after SAST/SCA] --> CR[code_reviewer.py]
    CR -->|reads| SRC[app/app.py, capped at 20k chars]
    SRC --> TRYOLLAMA{Ollama + langchain-community importable and reachable?}
    TRYOLLAMA -->|yes| LC[LangChain LCEL: prompt pipe llm]
    LC --> CODELLAMA[Local Ollama - CodeLlama]
    CODELLAMA --> REVIEWOUT[reports/ai_code_review.json]
    TRYOLLAMA -->|no| STATICREV[Static fallback report, kept in sync with actual app.py state]
    STATICREV --> REVIEWOUT

    JENKINS --> HFA[hf_code_analyzer.py]
    HFA -->|reads| BANDIT[reports/bandit-report.json]
    BANDIT --> TRYHF{transformers importable?}
    TRYHF -->|yes| HFPIPE[HF text-classification pipeline pinned via HF_MODEL_REVISION]
    HFPIPE --> HFOUT[reports/hf_analysis.json - priority per finding]
    TRYHF -->|no| SAMPLEHF[Static sample report]
    SAMPLEHF --> HFOUT

    JENKINS --> CI[code_indexer.py]
    CI -->|reads| APPDIR[app/ directory]
    APPDIR --> TRYLI{llama-index importable?}
    TRYLI -->|yes| LIIDX[LlamaIndex VectorStoreIndex + Ollama Llama3 + HF embeddings]
    LIIDX --> DOCSOUT[docs/AUTO_GENERATED_README.md]
    TRYLI -->|no| STATICDOC[Static documentation]
    STATICDOC --> DOCSOUT

    REVIEWOUT --> MLF[mlflow_logger.py]
    HFOUT --> MLF
    DOCSOUT --> MLF
    MLF --> TRYMLF{MLflow tracking server reachable within 10s?}
    TRYMLF -->|yes| MLFLOG[MLflow run logged: params + metrics]
    TRYMLF -->|no, times out| SKIP[Skip logging, reports remain in reports/ for manual review]
```

## CI/CD Flow

```mermaid
flowchart TD
    DEV[Developer] -->|git push / PR| GIT[Git repository]
    GIT -->|webhook| JENKINS[Jenkins pipeline]
    JENKINS --> CHECKOUT[Checkout Code]
    CHECKOUT --> INSTALL[Install Dependencies - app + ai-agents, pinned]
    INSTALL --> LINT[Lint - flake8]
    LINT --> TEST[Unit Tests - pytest + coverage]
    TEST --> SAST[SAST - Bandit + Semgrep]
    SAST --> SONAR[SonarQube Analysis]
    SONAR --> SECRET[Secret Scan - gitleaks]
    SECRET --> SCA[Dependency Scan - Snyk + OWASP Dependency-Check]
    SCA --> AI[AI Code Review + HF Vuln Analysis + LlamaIndex Docs]
    AI --> MLFLOW[MLflow Logging]
    MLFLOW --> BUILD[Container Build]
    BUILD --> TRIVY[Container Scan - Trivy]
    TRIVY --> IAC[IaC Scan - checkov on terraform + kubernetes]
    IAC --> OPA[OPA Compliance Gate]
    OPA --> GATE{Security Gate - aggregate all findings}
    GATE -->|ENFORCE_SECURITY=false, default| DEPLOY[Deploy to Kubernetes]
    GATE -->|ENFORCE_SECURITY=true and HIGH/CRITICAL found| FAIL[Pipeline fails, build marked unstable]
    DEPLOY --> ZAP[DAST - OWASP ZAP baseline]
    ZAP --> VERIFY[Post-Deployment Verification - health check]
    VERIFY --> ARCHIVE[Archive all reports as Jenkins artifacts]
```

## Deployment Flow

```mermaid
flowchart LR
    IMG[Built + Trivy-scanned image] --> REG[(Container registry)]
    REG --> K8S{Deployment method}
    K8S -->|kubectl apply -f kubernetes/| PLAIN[Plain manifests: namespace, deployment, service, ingress, network-policy]
    K8S -->|helm install/upgrade| CHART[Helm chart: helm/devsecops-app]
    PLAIN --> NS[devsecops namespace]
    CHART --> NS
    NS --> PODS[2 replicas, non-root, read-only rootfs, seccomp, no capabilities]
    PODS --> PROBES[Liveness/Readiness probes hit /health]
    PROBES --> READY[Pods marked Ready, Service routes traffic]
    READY --> ING[Ingress with TLS termination]
```

## Incident Flow (what happens when a security issue is detected)

```mermaid
flowchart TD
    FIND[Scanner finds an issue: Bandit/Semgrep/Snyk/Trivy/gitleaks/checkov/ZAP] --> REPORT[Written to reports/*.json, archived as Jenkins artifact]
    REPORT --> GATE[security/security_gate.py aggregates all reports]
    GATE --> MODE{ENFORCE_SECURITY?}
    MODE -->|false, default| VISIBLE[Build continues; summary printed; reports available for human review]
    MODE -->|true| SEVCHECK{Any HIGH/CRITICAL or any secret found?}
    SEVCHECK -->|yes| BLOCK[Pipeline stage fails - deploy does not proceed]
    SEVCHECK -->|no| CONTINUE[Pipeline continues to deploy]
    BLOCK --> TRIAGE[Human triages the finding using the archived report]
    TRIAGE --> FIXORACCEPT{Fix or document as accepted risk?}
    FIXORACCEPT -->|fix| PATCH[Code/IaC change, re-run pipeline]
    FIXORACCEPT -->|accept| DOC[Documented in docs/SECURITY.md or docs/GAP_ANALYSIS.md with justification]
```
