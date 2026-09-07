pipeline {
    agent any

    parameters {
        booleanParam(name: 'ENFORCE_SECURITY', defaultValue: false, description: 'Fail the pipeline on high/critical security issues when true (Security Gate stage)')
    }

    environment {
        APP_IMAGE   = "ai-devsecops-app:${BUILD_NUMBER}"
        SONAR_HOST  = "${env.SONAR_HOST_URL ?: 'http://sonarqube:9000'}"
        APP_PORT    = "5001"
        PATH        = "/var/jenkins_home/.local/bin:${env.PATH}"
        // Was DOCKER_HOST=tcp://host.docker.internal:2375 — nothing listens there on this host, and
        // because this was a pipeline-wide env var, it silently broke every "docker" command in this
        // file, not just Trivy's (Container Build's `docker build` included) — masked everywhere by
        // `|| true`. Real docker access here is the mounted /var/run/docker.sock (docker's own
        // default), so this var should simply not be set.
        ENFORCE_SECURITY = "${params.ENFORCE_SECURITY}"
    }

    stages {
        stage('Checkout Code') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                echo 'Installing application and AI/LLM pipeline dependencies...'
                sh '''
                    python3 -m pip install --break-system-packages --quiet -r app/requirements.txt
                    # AI/LLM deps are pinned (ai-agents/requirements.txt) and installed once here rather than
                    # via runtime os.system("pip install ...") calls inside the AI scripts themselves — see
                    # ai-agents/requirements.txt for why. Non-fatal: if this install fails (e.g. no network,
                    # or torch's download budget is unavailable on this agent), every AI stage below still
                    # runs and degrades to its documented static fallback report instead of failing the build.
                    python3 -m pip install --break-system-packages --quiet -r ai-agents/requirements.txt || \
                        echo "⚠️ AI dependency install failed/skipped — AI stages will use static fallback reports"
                '''
            }
        }

        stage('Lint') {
            steps {
                echo 'Running flake8 lint...'
                sh '''
                    mkdir -p reports || true
                    python3 -m pip install --break-system-packages --quiet flake8
                    flake8 app --max-line-length=120 --format=default > reports/flake8-report.txt || true
                    cat reports/flake8-report.txt || true
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running pytest with coverage...'
                sh '''
                    mkdir -p reports || true
                    cd app && python3 -m pytest tests/ -v \
                        --cov=. --cov-report=xml:../reports/coverage.xml \
                        --junitxml=../reports/test-results.xml
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/test-results.xml'
                }
            }
        }

        stage('SAST (Bandit & Semgrep)') {
            steps {
                echo 'Running Bandit and Semgrep (SAST)...'
                sh '''
                    mkdir -p reports || true
                    bandit -r app -f json -o reports/bandit-report.json --severity-level medium || true
                    semgrep --config security/semgrep-rules.yaml app --json --output reports/semgrep-report.json || true
                '''
            }
        }

        stage('SonarQube Analysis') {
            steps {
                echo 'Running SonarQube static analysis...'
                sh '''
                    if command -v sonar-scanner >/dev/null 2>&1; then
                        sonar-scanner \
                          -Dsonar.host.url=${SONAR_HOST} \
                          -Dsonar.login=${SONAR_TOKEN:-} \
                          -Dsonar.python.coverage.reportPaths=reports/coverage.xml \
                          -Dsonar.python.bandit.reportPaths=reports/bandit-report.json || true
                    else
                        echo "⚠️ sonar-scanner not installed on this agent — skipping (see sonarqube/sonar-project.properties for config, docker-compose.yml runs a local SonarQube server for manual/CI use)"
                    fi
                '''
            }
        }

        stage('Secret Scan (gitleaks)') {
            steps {
                echo 'Scanning repository for hardcoded secrets...'
                sh '''
                    mkdir -p reports || true
                    if command -v gitleaks >/dev/null 2>&1; then
                        gitleaks detect --source=. --config=security/gitleaks.toml --report-format=json --report-path=reports/gitleaks-report.json --no-git || true
                    elif command -v docker >/dev/null 2>&1; then
                        docker run --rm -v "$(pwd)":/repo zricethezav/gitleaks:latest detect --source=/repo --config=/repo/security/gitleaks.toml --report-format=json --report-path=/repo/reports/gitleaks-report.json --no-git || true
                    else
                        echo "⚠️ Neither gitleaks binary nor Docker available on this agent — secret scan skipped, install one to enable this gate"
                    fi
                    if [ "${ENFORCE_SECURITY}" = "true" ] && [ -f reports/gitleaks-report.json ]; then
                        if [ -s reports/gitleaks-report.json ] && [ "$(cat reports/gitleaks-report.json)" != "[]" ]; then
                            echo "❌ gitleaks found potential secrets"; exit 1
                        fi
                    fi
                '''
            }
        }

        stage('Dependency Scan (Snyk & OWASP Dependency-Check)') {
            steps {
                echo 'Running Snyk and OWASP Dependency-Check...'
                sh '''
                    mkdir -p reports || true
                    # Snyk (requires SNYK_TOKEN in environment if using monitor/test with auth)
                    snyk test --file=app/requirements.txt --package-manager=pip --json > reports/snyk-report.json || true

                    # Optional enforcement: fail if high/critical found when ENFORCE_SECURITY=true
                    if [ "${ENFORCE_SECURITY}" = "true" ]; then
                      if command -v jq >/dev/null 2>&1 && [ -f reports/snyk-report.json ]; then
                        if jq '.vulnerabilities[]? | select(.severity=="high" or .severity=="critical")' reports/snyk-report.json | grep -q .; then
                          echo "Snyk found high/critical issues"; exit 1
                        fi
                      fi
                    fi

                    # OWASP Dependency-Check (uses bundled script in repo if available)
                    if [ -x security/dependency-check.sh ]; then
                      chmod +x security/dependency-check.sh || true
                      ./security/dependency-check.sh || true
                    else
                      echo 'dependency-check script not present or not executable' || true
                    fi
                '''
            }
        }

        stage('AI Code Review & Analysis & Docs') {
            steps {
                echo 'Running AI/LLM pipeline stages (LangChain code review, HuggingFace vulnerability analysis, LlamaIndex docs)...'
                sh '''
                    mkdir -p reports docs || true
                    # Order matters: hf_code_analyzer reads reports/bandit-report.json produced by the SAST
                    # stage above, and mlflow_logger (next stage) reads every report these three produce — so
                    # all three AI scripts must run BEFORE MLflow logging. Previously only code_reviewer.py was
                    # called here, so hf_analysis.json and AUTO_GENERATED_README.md never existed for
                    # mlflow_logger to log — see docs/GAP_ANALYSIS.md.
                    python3 ai-agents/code_reviewer.py || true
                    python3 ai-agents/hf_code_analyzer.py || true
                    python3 ai-agents/code_indexer.py || true
                '''
            }
        }

        stage('MLflow Logging') {
            steps {
                echo 'Logging all AI runs to MLflow...'
                sh '''
                    python3 ai-agents/mlflow_logger.py || true
                '''
            }
        }

        stage('Container Build') {
            steps {
                echo 'Building application container image...'
                sh '''
                    docker build -t ${APP_IMAGE} -f app/Dockerfile . || true
                '''
            }
        }

        stage('Container Scan (Trivy)') {
            steps {
                echo 'Running Trivy container scan...'
                sh '''
                    mkdir -p reports || true
                    # Was `-e DOCKER_HOST=${DOCKER_HOST}` (tcp://host.docker.internal:2375) — nothing
                    # listens on that TCP port on this host (real docker access here is the mounted
                    # /var/run/docker.sock, same as every other stage), so the trivy container could
                    # never actually connect to inspect ${APP_IMAGE} — masked by `|| true` into a
                    # silently-empty report. Mount the real socket instead.
                    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/trivy aquasec/trivy:latest image --format json --severity HIGH,CRITICAL ${APP_IMAGE} > reports/trivy-report.json || true
                '''
            }
        }

        stage('IaC Scan (checkov)') {
            steps {
                echo 'Scanning Terraform and Kubernetes manifests for misconfigurations...'
                sh '''
                    mkdir -p reports || true
                    if command -v checkov >/dev/null 2>&1; then
                        checkov -d terraform --output json --quiet > reports/checkov-terraform.json || true
                        checkov -d kubernetes --framework kubernetes --output json --quiet > reports/checkov-kubernetes.json || true
                    else
                        python3 -m pip install --break-system-packages --quiet checkov && \
                        checkov -d terraform --output json --quiet > reports/checkov-terraform.json || true
                        checkov -d kubernetes --framework kubernetes --output json --quiet > reports/checkov-kubernetes.json || true
                    fi
                '''
            }
        }

        stage('OPA Compliance Gate') {
            steps {
                echo 'Evaluating OPA policies (compliance)...'
                sh '''
                    chmod +x security/test_policy.sh || true
                    ./security/test_policy.sh || true
                '''
            }
        }

        stage('Security Gate') {
            steps {
                echo 'Aggregating security scan results into a single pass/fail decision...'
                sh '''
                    mkdir -p reports || true
                    # Centralizes the enforcement decision that was previously scattered per-tool (only Snyk
                    # had an ENFORCE_SECURITY check). Default is non-blocking (matches this repo's documented
                    # "shift-left without blocking early dev cycles" philosophy, see README.md) — set
                    # ENFORCE_SECURITY=true to make this stage fail the build on HIGH/CRITICAL findings.
                    python3 security/security_gate.py --enforce="${ENFORCE_SECURITY}" || GATE_EXIT=$?
                    exit ${GATE_EXIT:-0}
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                echo 'Deploying to Kubernetes...'
                sh '''
                    mkdir -p reports || true
                    KUBECONFIG_FILE=/etc/rancher/k3s/k3s.yaml
                    CLUSTER_OK=false
                    if [ -f "${KUBECONFIG_FILE}" ] && kubectl --kubeconfig="${KUBECONFIG_FILE}" get nodes >/dev/null 2>&1; then
                        CLUSTER_OK=true
                    fi

                    if [ "${CLUSTER_OK}" = "true" ] && [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
                        # Real deploy: push the image this same build just produced (Container Build
                        # stage, ${APP_IMAGE}) to Docker Hub, then point Helm's chart at it. This is
                        # the path a stock Jenkins-in-Docker + k3s setup can actually complete without
                        # any Docker-daemon-to-containerd bridge (k3s pulls over the network like any
                        # other cluster would) — see docs/EC2_DEPLOYMENT_GUIDE.md Part E for the
                        # equivalent manual, no-registry-needed command using a local image import,
                        # which stays the simpler option when you don't want a Docker Hub repo.
                        echo "🚀 Deploying ${APP_IMAGE} to Kubernetes via Docker Hub + Helm..."
                        echo "${DOCKERHUB_TOKEN}" | docker login -u "${DOCKERHUB_USERNAME}" --password-stdin
                        docker tag "${APP_IMAGE}" "${DOCKERHUB_USERNAME}/devsecops-app:${BUILD_NUMBER}"
                        docker push "${DOCKERHUB_USERNAME}/devsecops-app:${BUILD_NUMBER}"
                        kubectl --kubeconfig="${KUBECONFIG_FILE}" apply -f kubernetes/namespace.yaml || true
                        helm --kubeconfig="${KUBECONFIG_FILE}" upgrade --install devsecops-app ./helm/devsecops-app \
                            --namespace default \
                            --set image.repository="${DOCKERHUB_USERNAME}/devsecops-app" \
                            --set image.tag="${BUILD_NUMBER}" \
                            --wait --timeout 120s \
                            && echo "✅ Deployed ${DOCKERHUB_USERNAME}/devsecops-app:${BUILD_NUMBER}" \
                            || echo "⚠️ Helm deploy failed — see log above. Non-blocking, matches this repo's scan-stage philosophy (see docs/SECURITY.md)."
                    else
                        # Honest skip, not silent no-op: previously this stage always applied
                        # security/examples/good-deployment.yaml — a throwaway OPA-policy demo
                        # manifest (different Deployment name, a registry image that doesn't exist)
                        # — regardless of whether a real deploy was possible, which looked like a
                        # working "Deploy" stage without actually deploying this build's app anywhere
                        # reachable. Now: deploy for real when it's actually possible, otherwise say so.
                        if [ "${CLUSTER_OK}" != "true" ]; then
                            echo "⚠️ No reachable Kubernetes cluster at ${KUBECONFIG_FILE} on this agent — skipping real deploy."
                        else
                            echo "⚠️ DOCKERHUB_USERNAME/DOCKERHUB_TOKEN not set — skipping real deploy (see .env.example)."
                        fi
                        echo "⚠️ See docs/EC2_DEPLOYMENT_GUIDE.md Part E to deploy manually without needing a registry."
                        echo "⚠️ Applying the OPA-policy demo manifest instead, so the OPA Compliance Gate stage still has a live example to point at if you inspect the cluster by hand."
                        kubectl --kubeconfig="${KUBECONFIG_FILE}" apply -f kubernetes/namespace.yaml 2>/dev/null || true
                        kubectl --kubeconfig="${KUBECONFIG_FILE}" apply -f security/examples/good-deployment.yaml 2>/dev/null || true
                    fi
                '''
            }
        }

        stage('Dynamic Security Scan (OWASP ZAP)') {
            steps {
                echo 'Running OWASP ZAP dynamic scan against deployed app...'
                sh '''
                    mkdir -p reports || true
                    chmod +x security/zap-runner.sh || true
                    ./security/zap-runner.sh || true
                '''
            }
        }

        stage('Post-Deployment Verification') {
            steps {
                echo 'Smoke-testing the deployed application health endpoint...'
                sh '''
                    curl -fsS --max-time 10 "http://devsecops-app:5000/health" && echo "✅ health check passed" || echo "⚠️ health check failed or target unreachable from this agent"
                '''
            }
        }
    }

    post {
        always {
            echo 'Archiving reports...'
            archiveArtifacts artifacts: 'reports/**/*', allowEmptyArchive: true
        }

        success {
            echo 'Pipeline completed successfully.'
        }

        failure {
            echo 'Pipeline failed. Check the logs.'
        }
    }
}
