pipeline {
    agent any

    environment {
        APP_IMAGE  = "ai-devsecops-app:${BUILD_NUMBER}"
        SONAR_HOST = "http://sonarqube:9000"
        APP_PORT   = "5001"
        PATH       = "/var/jenkins_home/.local/bin:${env.PATH}"
        DOCKER_HOST = "tcp://host.docker.internal:2375"
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                echo 'Installing Python dependencies...'
                sh '''
                    pip install --break-system-packages -r app/requirements.txt
                    pip install --break-system-packages bandit semgrep pytest pytest-cov safety
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                echo 'Running unit tests...'
                sh '''
                    mkdir -p reports
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

        stage('Bandit Security Scan') {
            steps {
                echo 'Running Bandit security scan...'
                sh '''
                    mkdir -p reports
                    bandit -r app \
                        -f json \
                        -o reports/bandit-report.json \
                        --severity-level medium || true
                '''
            }
        }

        stage('Semgrep Security Scan') {
            steps {
                echo 'Running Semgrep security scan...'
                sh '''
                    mkdir -p reports
                    semgrep --config security/semgrep-rules.yaml app \
                        --json \
                        --output reports/semgrep-report.json || true
                '''
            }
        }

        stage('Dependency Check') {
            steps {
                echo 'Running dependency security check...'
                sh '''
                    mkdir -p reports
                    safety check \
                        -r app/requirements.txt \
                        --json > reports/dependency-check.json || true
                '''
            }
        }

        stage('SonarQube Analysis') {
            steps {
                echo 'Running SonarQube analysis...'
                script {
                    def scannerHome = tool 'SonarScanner'

                    withSonarQubeEnv('SonarQube') {
                        sh """
                            ${scannerHome}/bin/sonar-scanner \
                              -Dsonar.projectKey=ai-devsecops-pipeline \
                              -Dsonar.sources=app \
                              -Dsonar.host.url=${SONAR_HOST} \
                              -Dsonar.python.coverage.reportPaths=reports/coverage.xml
                        """
                    }
                }
            }
        }

        stage('AI Code Review') {
            steps {
                echo 'Running AI code review...'
                sh '''
                    pip install --break-system-packages \
                        langchain \
                        langchain-community \
                        ollama -q

                    python ai-agents/code_reviewer.py || true
                '''
            }
        }

        stage('HuggingFace Analysis') {
            steps {
                echo 'Running HuggingFace analysis...'
                sh '''
                    pip install --break-system-packages transformers -q
                    pip install --break-system-packages \
                        torch \
                        --index-url https://download.pytorch.org/whl/cpu -q

                    python ai-agents/hf_code_analyzer.py || true
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image...'
                sh '''
                    docker build -t ${APP_IMAGE} ./app
                '''
            }
        }

        stage('Trivy Container Scan') {
            steps {
                echo 'Running Trivy scan...'
                sh '''
                    mkdir -p reports

                    docker run --rm \
                        -e DOCKER_HOST=${DOCKER_HOST} \
                        -v trivy-cache:/root/.cache/trivy \
                        aquasec/trivy:latest image \
                        --timeout 30m \
                        --format json \
                        --severity HIGH,CRITICAL \
                        ${APP_IMAGE} > reports/trivy-report.json || true
                '''
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying application...'
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

                    sleep 10
                '''
            }
        }

        stage('OWASP ZAP DAST Scan') {
            steps {
                echo 'Running OWASP ZAP scan via zap-runner...'
                sh '''
                    mkdir -p reports
                    chmod +x security/zap-runner.sh || true
                    ./security/zap-runner.sh
                '''
            }
        }

        stage('AI Vulnerability Analysis') {
            steps {
                echo 'Running AI vulnerability analysis...'
                sh '''
                    python ai-agents/hf_code_analyzer.py || true
                '''
            }
        }

        stage('AI Documentation') {
            steps {
                echo 'Generating documentation...'
                sh '''
                    pip install --break-system-packages \
                        llama-index \
                        llama-index-llms-ollama -q

                    python ai-agents/code_indexer.py || true
                '''
            }
        }

        stage('MLflow Tracking') {
            steps {
                echo 'Logging results to MLflow...'
                sh '''
                    pip install --break-system-packages mlflow -q
                    python ai-agents/mlflow_logger.py || true
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
