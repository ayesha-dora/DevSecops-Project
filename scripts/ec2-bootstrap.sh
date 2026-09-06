#!/usr/bin/env bash
# ec2-bootstrap.sh — one-time setup for a single-EC2, budget-friendly deployment of
# DevSecOps-CI-CD-Project. See docs/EC2_DEPLOYMENT_GUIDE.md for the full walkthrough this
# script is one step of. Idempotent-ish: safe to re-run if a step fails partway.
#
# Target: Ubuntu 22.04 LTS EC2 instance (t3.large recommended — see the guide's sizing table).
# Run as: sudo bash scripts/ec2-bootstrap.sh
#
# What this installs:
#   Docker + Compose plugin      -> runs this repo's docker-compose.yml toolchain
#   k3s (Traefik disabled)       -> the actual Kubernetes target for the app (satisfies the
#                                    exam's "deploy to Kubernetes" requirement)
#   ingress-nginx (via Helm)     -> matches this repo's Ingress manifests, which hardcode
#                                    ingress class "nginx"
#   cert-manager (via Helm)      -> free, real HTTPS via Let's Encrypt (no domain purchase
#                                    needed — see the guide's sslip.io section)
#   kubectl, Helm, AWS CLI v2    -> cluster/registry tooling
#   checkov, trivy, gitleaks, opa -> the scanners this repo's Jenkinsfile already calls
#
# What this does NOT do: clone the repo, write .env, build the app image, or deploy anything.
# Those are separate steps in the guide, done after this script finishes.
set -euo pipefail

TARGET_USER="${SUDO_USER:-ubuntu}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"

echo "=== 1/12: System update ==="
apt-get update -y
apt-get upgrade -y

echo "=== 2/12: Swap file (safety net — this stack is memory-heavy for one box) ==="
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Created 4G swapfile."
else
    echo "Swapfile already present, skipping."
fi

echo "=== 3/12: Kernel tuning required by SonarQube's embedded Elasticsearch ==="
sysctl -w vm.max_map_count=262144
grep -q '^vm.max_map_count' /etc/sysctl.conf || echo 'vm.max_map_count=262144' >> /etc/sysctl.conf

echo "=== 4/12: Base packages ==="
apt-get install -y ca-certificates curl gnupg git unzip jq python3-pip apt-transport-https software-properties-common lsb-release

echo "=== 5/12: Docker + Compose plugin ==="
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "Docker already installed, skipping."
fi
usermod -aG docker "${TARGET_USER}"

echo "=== 6/12: k3s (lightweight Kubernetes — Traefik disabled, we install ingress-nginx instead) ==="
if ! command -v k3s >/dev/null 2>&1; then
    curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik --write-kubeconfig-mode 644" sh -
else
    echo "k3s already installed, skipping."
fi

mkdir -p "${TARGET_HOME}/.kube"
cp /etc/rancher/k3s/k3s.yaml "${TARGET_HOME}/.kube/config"
chown -R "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/.kube"
grep -q 'KUBECONFIG=' "${TARGET_HOME}/.bashrc" 2>/dev/null || echo 'export KUBECONFIG=$HOME/.kube/config' >> "${TARGET_HOME}/.bashrc"

echo "=== 7/12: kubectl (upstream binary, for convenience alongside k3s's bundled one) ==="
if ! command -v kubectl >/dev/null 2>&1; then
    KVER="$(curl -L -s https://dl.k8s.io/release/stable.txt)"
    curl -LO "https://dl.k8s.io/release/${KVER}/bin/linux/amd64/kubectl"
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm -f kubectl
fi

echo "=== 8/12: Helm 3 ==="
if ! command -v helm >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo "Waiting for k3s to be ready..."
for i in $(seq 1 30); do
    kubectl get nodes >/dev/null 2>&1 && break
    sleep 2
done
kubectl get nodes

echo "=== 9/12: ingress-nginx (matches this repo's Ingress 'class: nginx') ==="
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace \
    --set controller.service.type=LoadBalancer \
    --set controller.watchIngressWithoutClass=true

echo "=== 10/12: cert-manager (free Let's Encrypt TLS — see the guide's sslip.io section) ==="
helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace cert-manager --create-namespace \
    --set crds.enabled=true

echo "=== 11/12: AWS CLI v2 (optional — only needed if you push images to ECR instead of importing locally) ==="
if ! command -v aws >/dev/null 2>&1; then
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    unzip -q -o /tmp/awscliv2.zip -d /tmp
    /tmp/aws/install
    rm -rf /tmp/awscliv2.zip /tmp/aws
fi

echo "=== 12/12: Security/scanner CLIs used by the Jenkinsfile ==="
pip3 install --break-system-packages --quiet checkov || pip3 install --quiet checkov

if ! command -v trivy >/dev/null 2>&1; then
    curl -sfL https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg
    echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" \
        | tee /etc/apt/sources.list.d/trivy.list > /dev/null
    apt-get update -y
    apt-get install -y trivy
fi

if ! command -v gitleaks >/dev/null 2>&1; then
    GITLEAKS_VER="8.18.4"
    curl -sL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VER}/gitleaks_${GITLEAKS_VER}_linux_x64.tar.gz" -o /tmp/gitleaks.tgz
    tar -xzf /tmp/gitleaks.tgz -C /usr/local/bin gitleaks
    rm -f /tmp/gitleaks.tgz
fi

if ! command -v opa >/dev/null 2>&1; then
    curl -sL -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static
    chmod +x /usr/local/bin/opa
fi

echo ""
echo "=================================================================="
echo " Bootstrap complete."
echo " Log out and back in (or run 'newgrp docker') so the docker group takes effect."
echo " Next steps: docs/EC2_DEPLOYMENT_GUIDE.md, starting at 'Part C'."
echo "=================================================================="
