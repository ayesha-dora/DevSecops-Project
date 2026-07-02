# AI-Augmented DevSecOps Pipeline
### EduQual Level 6 — Diploma in Artificial Intelligence Operations

---

## Project Overview

This project implements a complete **AI-Augmented DevSecOps Pipeline** that integrates:
- **CI/CD Automation** via Jenkins (16-stage pipeline)
- **AI Code Review** via LangChain + CodeLlama
- **Vulnerability Classification** via HuggingFace Transformers
- **Auto Documentation** via LlamaIndex + Llama3
- **AI Model Tracking** via MLflow
- **Security Scanning** via Bandit, Semgrep, Trivy, OWASP ZAP
- **Code Quality** via SonarQube
- **Monitoring** via Prometheus + Grafana

---

## Tools & Technologies

| Category | Tool | Purpose |
|----------|------|---------|
| CI/CD | Jenkins | Pipeline automation |
| Code Quality | SonarQube | Static code analysis |
| SAST | Bandit + Semgrep | Python security scanning |
| DAST | OWASP ZAP | Runtime security testing |
| Container Security | Trivy | Docker image scanning |
| Dependency Check | Safety | Python package CVE scanning |
| AI Framework | LangChain | Code review automation |
| AI Framework | HuggingFace | Vulnerability classification |
| AI Framework | LlamaIndex | Documentation generation |
| LLM Backend | Ollama (CodeLlama, Llama3) | Local AI model serving |
| Model Tracking | MLflow | AI experiment tracking |
| Monitoring | Prometheus + Grafana | Pipeline observability |

---

## Architecture

```
Developer → Git Push → Jenkins Pipeline
                            │
                ┌───────────┴───────────┐
                │    16 Pipeline Stages  │
                └───────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   Security Tools      AI Agents           Quality Tools
   ├── Bandit           ├── LangChain       ├── SonarQube
   ├── Semgrep          ├── HuggingFace     └── Unit Tests
   ├── Trivy            ├── LlamaIndex
   ├── ZAP              └── MLflow
   └── Safety
        │                   │
        └───────────────────┘
                    │
            Reports & Dashboards
            ├── Jenkins UI (localhost:8080)
            ├── SonarQube (localhost:9000)
            ├── MLflow (localhost:5000)
            └── Grafana (localhost:3000)
```

---

## Quick Start

### Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Ollama (https://ollama.ai)

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/ai-devsecops-pipeline.git
cd ai-devsecops-pipeline
```

### 2. Start All Services
```bash
docker-compose up -d
```

### 3. Verify Services Running
```
Jenkins    → http://localhost:8080
SonarQube  → http://localhost:9000
Prometheus → http://localhost:9090
Grafana    → http://localhost:3000  (admin/admin123)
MLflow     → http://localhost:5000
ZAP        → http://localhost:8090
```

### 4. Install AI Dependencies
```bash
pip install langchain langchain-community transformers mlflow \
            llama-index llama-index-llms-ollama ollama
```

### 5. Download AI Models
```bash
ollama pull codellama
ollama pull llama3
```

### 6. Run AI Agents Locally
```bash
python ai-agents/code_reviewer.py
python ai-agents/hf_code_analyzer.py
python ai-agents/code_indexer.py
python ai-agents/mlflow_logger.py
```

---

## Compliance & Standards

| Standard | Implementation |
|----------|---------------|
| **ISO/IEC 42001** | MLflow tracks all AI model usage, decisions, and outputs |
| **NIST AI RMF** | Risk documented, AI outputs reviewed before deployment |
| **GDPR** | No personal data stored, all data processed locally |

---

