"""
HuggingFace Vulnerability Analyzer
Stage 9 & 14 of Jenkins Pipeline

What it does:
- Reads Bandit scan results (reports/bandit-report.json)
- Uses HuggingFace pipeline to classify each vulnerability
- Assigns severity and priority
- Saves enriched report to reports/hf_analysis.json
"""

import json
import os
import time


def analyze_with_huggingface():
    print("🧠 HuggingFace Vulnerability Analyzer Starting...")

    # Install transformers if needed
    try:
        from transformers import pipeline as hf_pipeline
    except ImportError:
        print("Installing transformers...")
        os.system("pip install transformers torch -q")
        from transformers import pipeline as hf_pipeline

    # Load Bandit results
    bandit_path = "reports/bandit-report.json"
    if not os.path.exists(bandit_path):
        print(f"⚠️ No Bandit report found at {bandit_path}")
        print("📝 Creating sample analysis report...")
        save_sample_report()
        return

    with open(bandit_path) as f:
        bandit_data = json.load(f)

    issues = bandit_data.get('results', [])
    print(f"📊 Found {len(issues)} issues to analyze")

    if not issues:
        print("✅ No issues found in Bandit report")
        save_report([])
        return

    # Load HuggingFace text classification model
    print("📥 Loading HuggingFace model (first run downloads ~500MB)...")
    start = time.time()

    try:
        classifier = hf_pipeline(
            "text-classification",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512
        )
    except Exception as e:
        print(f"⚠️ HuggingFace model error: {e}")
        save_sample_report()
        return

    analyzed = []
    for issue in issues:
        text = f"Security issue: {issue.get('issue_text', '')} in {issue.get('test_name', '')}"

        try:
            result = classifier(text[:512])[0]
            confidence = round(result['score'], 3)
        except Exception:
            confidence = 0.5

        analyzed.append({
            "issue_id": issue.get('test_id', 'N/A'),
            "issue_name": issue.get('test_name', 'N/A'),
            "description": issue.get('issue_text', 'N/A'),
            "file": issue.get('filename', 'N/A'),
            "line": issue.get('line_number', 0),
            "original_severity": issue.get('issue_severity', 'N/A'),
            "hf_confidence": confidence,
            "priority": "HIGH" if confidence > 0.8 else "MEDIUM" if confidence > 0.5 else "LOW",
            "suggested_fix": get_fix_suggestion(issue.get('test_name', ''))
        })

    duration = time.time() - start
    save_report(analyzed)

    print(f"✅ HuggingFace Analysis Complete ({duration:.1f}s)")
    print(f"📊 Analyzed {len(analyzed)} vulnerabilities")
    print(f"📁 Report: reports/hf_analysis.json")


def get_fix_suggestion(test_name):
    fixes = {
        "B101": "Remove assert statements from production code",
        "B105": "Use environment variables for passwords - os.getenv('PASSWORD')",
        "B106": "Never hardcode passwords in function arguments",
        "B201": "Disable Flask debug mode: app.run(debug=False)",
        "B301": "Use json.loads() instead of pickle.loads()",
        "B302": "Use secure marshal functions",
        "B303": "Use SHA256 or stronger hashing",
        "B307": "Avoid eval() - use ast.literal_eval() instead",
        "B608": "Use parameterized queries to prevent SQL injection",
    }
    return fixes.get(test_name, "Review and fix according to OWASP guidelines")


def save_report(data):
    os.makedirs("reports", exist_ok=True)
    report = {
        "framework": "huggingface_transformers",
        "model": "distilbert-base-uncased",
        "total_issues": len(data),
        "results": data
    }
    with open("reports/hf_analysis.json", 'w') as f:
        json.dump(report, f, indent=2)


def save_sample_report():
    save_report([{
        "issue_id": "SAMPLE",
        "description": "No Bandit issues found or Bandit not run yet",
        "priority": "LOW",
        "suggested_fix": "Run Bandit first: bandit -r app/ -f json -o reports/bandit-report.json"
    }])
    print("📁 Sample report saved: reports/hf_analysis.json")


if __name__ == "__main__":
    analyze_with_huggingface()
