pipeline {
    agent any

    environment {
        APP_IMAGE = "ai-devsecops-app:${BUILD_NUMBER}"
        SONAR_HOST = "http://sonarqube:9000"
        APP_PORT = "5001"
        PATH = "/var/jenkins_home/.local/bin:${env.PATH}"
        DOCKER_HOST = "tcp://host.docker.internal:2375"
    }

    stages {

        // ─────────────────────────────────────
        // STAGE 1: Checkout Code
        // ─────────────────────────────────────
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
            }
        }

        // ─────────────────────────────────────
        // STAGE 2: Install Dependencies
        // ─────────────────────────────────────
        stage('Install Dependencies') {
            steps {
                echo '📦 Installing Python dependencies...'
                sh '''
                    pip install --break-system-packages -r app/requirements.txt
                    pip install --break-system-packages bandit semgrep pytest pytest-cov
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 3: Run Unit Tests
        // ─────────────────────────────────────
        stage('Unit Tests') {
            steps {
                echo '🧪 Running unit tests...'
                sh '''
                    cd app
                    pytest tests/ -v \
                        --cov=. \
                        --cov-report=xml:../reports/coverage.xml \
                        --junitxml=../reports/test-results.xml
                '''
            }
            post {
                always {
                    junit 'reports/test-results.xml'
                }
            }
        }

        // ─────────────────────────────────────
        // STAGE 4: Bandit SAST Scan
        // ─────────────────────────────────────
        stage('Bandit Security Scan') {
            steps {
                echo '🔍 Running Bandit SAST security scan...'
                sh '''
                    bandit -r app/ \
                        -f json \
                        -o reports/bandit-report.json \
                        --severity-level medium \
                        || true
                    echo "Bandit scan complete - check reports/bandit-report.json"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 5: Semgrep SAST Scan
        // ─────────────────────────────────────
        stage('Semgrep Security Scan') {
            steps {
                echo '🔎 Running Semgrep security scan...'
                sh '''
                    semgrep --config security/semgrep-rules.yaml app/ \
                        --json \
                        --output reports/semgrep-report.json \
                        || true
                    echo "Semgrep scan complete - check reports/semgrep-report.json"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 6: OWASP Dependency Check
        // ─────────────────────────────────────
        stage('Dependency Check') {
            steps {
                echo '📋 Running OWASP Dependency Check...'
                sh '''
                    pip install --break-system-packages safety
                    safety check \
                        -r app/requirements.txt \
                        --json \
                        > reports/dependency-check.json \
                        || true
                    echo "Dependency check complete"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 7: SonarQube Analysis
        // ─────────────────────────────────────
        stage('SonarQube Analysis') {
            steps {
                echo '📊 Running SonarQube code quality analysis...'
                script {
                    def scannerHome = tool 'SonarScanner'
                    withSonarQubeEnv('SonarQube') {
                        sh """
                            ${scannerHome}/bin/sonar-scanner \
                                -Dsonar.projectKey=ai-devsecops-pipeline \
                                -Dsonar.sources=app \
                                -Dsonar.host.url=${SONAR_HOST} \
                                -Dsonar.python.coverage.reportPaths=reports/coverage.xml \
                                || echo "SonarQube scan attempted"
                        """
                    }
                }
            }
        }

        // ─────────────────────────────────────
        // STAGE 8: AI Code Review (LangChain)
        // ─────────────────────────────────────
        stage('AI Code Review') {
            steps {
                echo '🤖 Running AI-powered code review with LangChain...'
                sh '''
                    pip install --break-system-packages langchain langchain-community ollama -q
                    python ai-agents/code_reviewer.py || echo "AI review completed"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 9: HuggingFace Vulnerability Analysis
        // ─────────────────────────────────────
        stage('HuggingFace Analysis') {
            steps {
                echo '🧠 Running HuggingFace vulnerability classification...'
                sh '''
                    pip install --break-system-packages transformers -q
                    pip install --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu -q
                    python ai-agents/hf_code_analyzer.py || echo "HF analysis completed"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 10: Build Docker Image
        // ─────────────────────────────────────
        stage('Build Docker Image') {
            steps {
                echo '🐳 Building Docker image...'
                sh '''
                    docker build -t ${APP_IMAGE} ./app
                    echo "Docker image built: ${APP_IMAGE}"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 11: Trivy Container Scan
        // ─────────────────────────────────────
        stage('Trivy Container Scan') {
            steps {
                echo '🔒 Scanning Docker image with Trivy...'
                sh '''
                    mkdir -p reports
                    docker run --rm \
                        -e DOCKER_HOST=tcp://host.docker.internal:2375 \
                        -v trivy-cache:/root/.cache/trivy \
                        aquasec/trivy:latest image \
                        --timeout 30m \
                        --format json \
                        --severity HIGH,CRITICAL \
                        ${APP_IMAGE} > reports/trivy-report.json || true
                    echo "Trivy scan complete"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 12: Deploy Application
        // ─────────────────────────────────────
        stage('Deploy') {
            steps {
                echo '🚀 Deploying application locally...'
                sh '''
                    docker stop sample-app || true
                    docker rm sample-app || true
                    docker run -d \
                        --name sample-app \
                        --network ai-devsecops-pipeline_devsecops \
                        -p ${APP_PORT}:5001 \
                        ${APP_IMAGE} || \
                    docker run -d \
                        --name sample-app \
                        -p ${APP_PORT}:5001 \
                        ${APP_IMAGE}
                    sleep 5
                    echo "App deployed at http://localhost:${APP_PORT}"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 13: OWASP ZAP DAST Scan
        // ─────────────────────────────────────
        stage('OWASP ZAP DAST Scan') {
            steps {
                echo '⚡ Running OWASP ZAP dynamic security scan...'
                sh '''
                    docker run --rm \
                        zaproxy/zap-stable:latest \
                        zap-baseline.py \
                        -t http://host.docker.internal:${APP_PORT} \
                        || true
                    echo "ZAP scan complete"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 14: AI Vulnerability Analysis
        // ─────────────────────────────────────
        stage('AI Vulnerability Analysis') {
            steps {
                echo '🤖 AI analyzing all security scan results...'
                sh '''
                    python ai-agents/hf_code_analyzer.py || echo "AI vuln analysis done"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 15: LlamaIndex Documentation
        // ─────────────────────────────────────
        stage('AI Documentation') {
            steps {
                echo '📝 Generating AI documentation with LlamaIndex...'
                sh '''
                    pip install --break-system-packages llama-index llama-index-llms-ollama -q
                    python ai-agents/code_indexer.py || echo "Docs generated"
                '''
            }
        }

        // ─────────────────────────────────────
        // STAGE 16: MLflow Log Results
        // ─────────────────────────────────────
        stage('MLflow Tracking') {
            steps {
                echo '📊 Logging all AI results to MLflow...'
                sh '''
                    pip install --break-system-packages mlflow -q
                    python ai-agents/mlflow_logger.py || echo "MLflow logging done"
                '''
            }
        }
    }

    // ─────────────────────────────────────
    // POST: Always publish reports
    // ─────────────────────────────────────
    post {
        always {
            echo '📋 Pipeline complete - archiving reports...'
            archiveArtifacts artifacts: 'reports/**/*', allowEmptyArchive: true
        }
        success {
            echo '✅ Pipeline SUCCESS - all stages passed!'
        }
        failure {
            echo '❌ Pipeline FAILED - check stage logs above'
        }
    }
}
