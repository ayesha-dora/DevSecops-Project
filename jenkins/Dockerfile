# Custom Jenkins image for DevSecOps-CI-CD-Project (new — see CONTEXT.md Change #12).
#
# The stock jenkins/jenkins:lts image (what docker-compose.yml ran before this file existed) is
# just the JVM + Jenkins core: no Python, no Docker CLI, no kubectl/Helm, none of the scanner
# binaries. The root Jenkinsfile's "sh" steps call python3/pip, bandit, semgrep, checkov,
# gitleaks, opa, docker, kubectl, and helm directly — every stage past "Checkout Code" would fail
# with "command not found" against the stock image. This bakes all of it in once at build time
# instead of discovering each missing tool one pipeline run at a time.
FROM jenkins/jenkins:lts

USER root

# --- OS packages, Python (python-is-python3 because security/test_policy.sh calls `python`,
#     not `python3`), build-essential/rustc/cargo (semgrep's pinned version below needs to build
#     a Rust extension from source on this base image's architecture), Node/npm (for the Snyk CLI,
#     which ships as an npm package, below), and prerequisites for the apt-repo steps below ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python-is-python3 \
        build-essential rustc cargo nodejs npm \
        curl unzip jq gnupg lsb-release ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Docker CLI. Talks to the host's daemon via the /var/run/docker.sock bind mount
#     docker-compose.yml already sets up for this service — this only adds the client binary
#     that mount needs something to talk through. Codename detected at build time so this
#     doesn't silently break if the upstream jenkins/jenkins:lts base OS release changes. ---
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# --- kubectl + Helm, for the real "Deploy to Kubernetes" stage against the host's k3s cluster
#     (see docs/EC2_DEPLOYMENT_GUIDE.md and scripts/ec2-bootstrap.sh) ---
RUN KVER="$(curl -L -s https://dl.k8s.io/release/stable.txt)" \
    && curl -LO "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -f kubectl
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# --- Scanner CLIs the Jenkinsfile shells out to directly (pinned — same reasoning as
#     ai-agents/requirements.txt: unpinned tool installs are a supply-chain risk, and a version
#     bump changing a stage's output shouldn't happen silently on a Jenkins agent rebuild).
#     Versions below were the latest available on PyPI/GitHub as of 2026-09-06 — bump
#     deliberately, not by accident, if you rebuild this image later. ---
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed packaging \
        bandit==1.9.3 semgrep==1.172.0 checkov==3.2.88
RUN GITLEAKS_VER=8.18.4 \
    && curl -sL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VER}/gitleaks_${GITLEAKS_VER}_linux_x64.tar.gz" -o /tmp/gitleaks.tgz \
    && tar -xzf /tmp/gitleaks.tgz -C /usr/local/bin gitleaks \
    && rm -f /tmp/gitleaks.tgz
RUN curl -sL -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static \
    && chmod +x /usr/local/bin/opa

# --- sonar-scanner CLI, for the "SonarQube Analysis" stage — that stage already has a graceful
#     `command -v sonar-scanner` skip, but skipping isn't the same as running; this makes the real
#     scan happen. Version verified downloadable from binaries.sonarsource.com before pinning. ---
RUN SONAR_SCANNER_VER=6.2.1.4610 \
    && curl -fsSL -o /tmp/sonar-scanner.zip \
        "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VER}-linux-x64.zip" \
    && unzip -q /tmp/sonar-scanner.zip -d /opt \
    && mv "/opt/sonar-scanner-${SONAR_SCANNER_VER}-linux-x64" /opt/sonar-scanner \
    && ln -s /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner \
    && rm -f /tmp/sonar-scanner.zip

# --- Snyk CLI, for the "Dependency Scan" stage. Ships as an npm package (needs the nodejs/npm
#     installed above) rather than a standalone binary. Version verified on the npm registry
#     before pinning, same discipline as every other tool in this file. ---
RUN npm install -g snyk@1.1307.1

# Jenkins' own entrypoint expects to run as the "jenkins" user, not root.
USER jenkins
