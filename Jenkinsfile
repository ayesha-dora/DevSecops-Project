pipeline {
    agent any

    parameters {
        booleanParam(name: 'ENFORCE_SECURITY', defaultValue: false, description: 'Fail the pipeline on high/critical security issues when true')
    }

    environment {
        APP_IMAGE  = "ai-devsecops-app:${BUILD_NUMBER}"
        SONAR_HOST = "http://sonarqube:9000"
        APP_PORT   = "5001"
        PATH       = "/var/jenkins_home/.local/bin:${env.PATH}"
        DOCKER_HOST = "tcp://host.docker.internal:2375"
        ENFORCE_SECURITY = "${params.ENFORCE_SECURITY}"
    }

    stages {
        stage('Checkout Code') {
            steps {
                echo 'Checking out source code...'
                checkout scm
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

        stage('AI Code Review & MLflow Logging') {
            steps {
                echo 'Running AI code review and MLflow logging...'
                sh '''
                    mkdir -p reports || true
                    python3 ai-agents/code_reviewer.py || true
                    python3 ai-agents/mlflow_logger.py || true
                '''
            }
        }

        stage('Container Scan (Trivy)') {
            steps {
                echo 'Building image and running Trivy container scan...'
                sh '''
                    mkdir -p reports || true
                    docker build -t ${APP_IMAGE} ./app || true
                    docker run --rm -e DOCKER_HOST=${DOCKER_HOST} -v trivy-cache:/root/.cache/trivy aquasec/trivy:latest image --format json --severity HIGH,CRITICAL ${APP_IMAGE} > reports/trivy-report.json || true
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

        stage('Deploy to Kubernetes') {
            steps {
                echo 'Deploying to Kubernetes (demo manifest)...'
                sh '''
                    # Apply example deployment (non-blocking)
                    kubectl apply -f security/examples/good-deployment.yaml || true
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
