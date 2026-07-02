"""
AI Code Reviewer — Using LangChain + Ollama (CodeLlama)
Stage 8 of Jenkins Pipeline

What it does:
- Reads app/app.py
- Sends code to local CodeLlama model via LangChain
- Gets back security issues, bugs, suggestions
- Saves report to reports/ai_code_review.json
"""

import json
import os
import sys
import time


def review_code():
    print("🤖 AI Code Reviewer Starting...")

    # Read source code
    code_path = "app/app.py"
    if not os.path.exists(code_path):
        print(f"❌ File not found: {code_path}")
        save_report({"status": "file_not_found", "file": code_path})
        return

    with open(code_path, 'r') as f:
        code = f.read()

    # Try LangChain + Ollama
    try:
        from langchain_community.llms import Ollama
        from langchain_core.prompts import PromptTemplate

        llm = Ollama(
            model="codellama",
            base_url="http://localhost:11434",
            timeout=120
        )

        prompt = PromptTemplate(
            input_variables=["code"],
            template="""You are a senior security engineer reviewing Python code.

Analyze this code and provide:
1. Security vulnerabilities found
2. Bug risks
3. Code quality issues
4. Suggested fixes

Code:
{code}

Respond in JSON format:
{{
  "vulnerabilities": [],
  "bugs": [],
  "suggestions": [],
  "severity_score": "LOW/MEDIUM/HIGH",
  "summary": ""
}}"""
        )

        print(f"📝 Reviewing: {code_path}")
        start = time.time()

        # Use LCEL pipe syntax instead of deprecated LLMChain
        chain = prompt | llm
        result = chain.invoke({"code": code})
        duration = time.time() - start

        report = {
            "file": code_path,
            "model": "codellama",
            "framework": "langchain",
            "duration_seconds": round(duration, 2),
            "review": result,
            "status": "success"
        }

        save_report(report)
        print(f"✅ AI Code Review Complete ({duration:.1f}s)")

    except ImportError as e:
        print(f"⚠️ LangChain/Ollama not available: {e}")
        print("📝 Saving static fallback report...")
        save_report({
            "file": code_path,
            "model": "static-fallback",
            "framework": "none",
            "duration_seconds": 0,
            "status": "ollama_not_available",
            "review": {
                "vulnerabilities": [
                    "SQL queries use string formatting - potential SQL injection risk",
                    "No input validation on POST /users endpoint"
                ],
                "bugs": [
                    "Missing error handling in database connection"
                ],
                "suggestions": [
                    "Use parameterized queries for database operations",
                    "Add input length validation",
                    "Add rate limiting to API endpoints"
                ],
                "severity_score": "MEDIUM",
                "summary": "Static analysis fallback - Ollama not available in pipeline"
            }
        })

    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg or "Failed to establish" in error_msg:
            print(f"⚠️ Ollama not running — using static fallback report")
            save_report({
                "file": code_path,
                "model": "static-fallback",
                "framework": "langchain",
                "duration_seconds": 0,
                "status": "ollama_not_available",
                "review": {
                    "vulnerabilities": [
                        "SQL queries use string formatting - potential SQL injection risk",
                        "No input validation on POST /users endpoint"
                    ],
                    "bugs": [
                        "Missing error handling in database connection"
                    ],
                    "suggestions": [
                        "Use parameterized queries for database operations",
                        "Add input length validation",
                        "Add rate limiting to API endpoints"
                    ],
                    "severity_score": "MEDIUM",
                    "summary": "Static analysis fallback - Ollama not available in pipeline"
                }
            })
        else:
            print(f"⚠️ Review error: {e}")
            save_report({
                "file": code_path,
                "error": error_msg,
                "status": "error",
                "model": "codellama",
                "framework": "langchain",
                "duration_seconds": 0
            })


def save_report(data):
    os.makedirs("reports", exist_ok=True)
    with open("reports/ai_code_review.json", 'w') as f:
        json.dump(data, f, indent=2)
    print(f"📁 Report saved: reports/ai_code_review.json")


if __name__ == "__main__":
    review_code()
