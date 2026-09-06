"""
MLflow AI Model Tracker
Stage 16 of Jenkins Pipeline

What it does:
- Reads all AI report files from reports/
- Logs each AI run to MLflow tracking server
- Records: model used, duration, issues found, framework
- Viewable at: http://localhost:5000
"""

import json
import os
import time


def log_all_to_mlflow():
    print("📊 MLflow Logger Starting...")
    print("🌐 MLflow UI: http://localhost:5000 or see MLFLOW_HOST env var")

    # MLflow must be pre-installed via requirements.txt
    try:
        import mlflow
    except ImportError as e:
        print(f"⚠️ MLflow not available: {e}")
        print("📝 Please install via: pip install -r ai-agents/requirements.txt")
        print("⚠️ Skipping MLflow logging - AI runs will still complete via fallback paths")
        return

    # Connect to MLflow server with timeout protection.
    # Default is 'mlflow' — the docker-compose service DNS name — because that's what this
    # script actually runs against in this repo's real topology: Jenkins and mlflow are both
    # services on the same 'devsecops' compose network (see docker-compose.yml). The previous
    # default, 'host.docker.internal', does NOT resolve on Linux Docker (which is what this
    # project's EC2 deployment uses) unless the container also has
    # `extra_hosts: ["host.docker.internal:host-gateway"]` set — which docker-compose.yml's
    # jenkins service now does, as a second, independent fix, so overriding MLFLOW_HOST back to
    # host.docker.internal (e.g. for a differently-shaped setup) still works too. If instead
    # running this script directly on the bare host (not inside any container), override to
    # 'localhost' — the mlflow service's port is also published there.
    mlflow_host = os.environ.get('MLFLOW_HOST', 'mlflow')
    tracking_uri = f"http://{mlflow_host}:5000"

    # Get timeout setting (default 10 seconds)
    timeout_seconds = int(os.environ.get('MLFLOW_CONNECT_TIMEOUT_SECONDS', '10'))

    # Set up timeout handler (Unix-only; timeout is best-effort on other platforms)
    import signal
    def timeout_handler(signum, frame):
        raise TimeoutError(f"MLflow connection timeout after {timeout_seconds}s")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)

    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("ai-devsecops-pipeline")
    except TimeoutError:
        print(f"⚠️ MLflow connection timed out after {timeout_seconds}s - skipping logging")
        return
    except Exception as e:
        print(f"⚠️ MLflow connection failed: {e} - skipping logging")
        return
    finally:
        signal.alarm(0)  # Cancel alarm

    build_number = os.environ.get('BUILD_NUMBER', 'local')
    print(f"🔢 Build: #{build_number}")

    # ── Log 1: AI Code Review (LangChain) ─────────────────
    log_code_review(mlflow, build_number)

    # ── Log 2: HuggingFace Analysis ───────────────────────
    log_hf_analysis(mlflow, build_number)

    # ── Log 3: LlamaIndex Documentation ───────────────────
    log_llamaindex(mlflow, build_number)

    print("✅ All AI runs logged to MLflow")
    print("📊 View dashboard: http://localhost:5000")


def log_code_review(mlflow, build_number):
    report_path = "reports/ai_code_review.json"
    if not os.path.exists(report_path):
        print("⚠️ No code review report found, skipping...")
        return

    with open(report_path) as f:
        data = json.load(f)

    with mlflow.start_run(run_name=f"langchain-code-review-{build_number}"):
        # Parameters (settings used)
        mlflow.log_param("framework", "langchain")
        mlflow.log_param("model", data.get("model", "codellama"))
        mlflow.log_param("build_number", build_number)
        mlflow.log_param("file_reviewed", data.get("file", "app/app.py"))
        mlflow.log_param("status", data.get("status", "unknown"))

        # Metrics (numbers)
        mlflow.log_metric("duration_seconds", data.get("duration_seconds", 0))

        print("✅ LangChain Code Review logged to MLflow")


def log_hf_analysis(mlflow, build_number):
    report_path = "reports/hf_analysis.json"
    if not os.path.exists(report_path):
        print("⚠️ No HuggingFace report found, skipping...")
        return

    with open(report_path) as f:
        data = json.load(f)

    results = data.get("results", [])
    high_count = sum(1 for r in results if r.get("priority") == "HIGH")
    medium_count = sum(1 for r in results if r.get("priority") == "MEDIUM")
    low_count = sum(1 for r in results if r.get("priority") == "LOW")

    with mlflow.start_run(run_name=f"huggingface-vuln-analysis-{build_number}"):
        mlflow.log_param("framework", "huggingface_transformers")
        mlflow.log_param("model", data.get("model", "distilbert"))
        mlflow.log_param("build_number", build_number)

        mlflow.log_metric("total_issues", data.get("total_issues", 0))
        mlflow.log_metric("high_priority", high_count)
        mlflow.log_metric("medium_priority", medium_count)
        mlflow.log_metric("low_priority", low_count)

        print(f"✅ HuggingFace Analysis logged: {high_count} HIGH, {medium_count} MEDIUM, {low_count} LOW")


def log_llamaindex(mlflow, build_number):
    docs_path = "docs/AUTO_GENERATED_README.md"
    if not os.path.exists(docs_path):
        print("⚠️ No LlamaIndex docs found, skipping...")
        return

    with mlflow.start_run(run_name=f"llamaindex-docs-{build_number}"):
        mlflow.log_param("framework", "llamaindex")
        mlflow.log_param("model", "llama3")
        mlflow.log_param("build_number", build_number)

        doc_size = os.path.getsize(docs_path)
        mlflow.log_metric("doc_size_bytes", doc_size)

        print(f"✅ LlamaIndex Documentation logged ({doc_size} bytes)")


if __name__ == "__main__":
    log_all_to_mlflow()
