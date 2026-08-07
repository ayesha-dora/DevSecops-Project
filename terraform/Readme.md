
# 🏗️ Terraform Infrastructure (AWS Cloud Setup - Optional)

This directory contains Infrastructure-as-Code (IaC) configurations written in Terraform to provision supporting AWS security and governance services in the **AWS Mumbai Region (`ap-south-1`)**[cite: 1].

---

## ⚠️ Important Note: AWS Integration is Optional

> **You DO NOT need an AWS account or cloud infrastructure to run and evaluate this DevSecOps pipeline.**

The core CI/CD pipeline, AI code review agents, local security scanners, and Kubernetes deployment workflows are fully functional in a **local environment** (e.g., using Minikube, Kind, or Docker Desktop Kubernetes) without deploying any AWS resources.

---

## 🚀 Execution Modes

### Option A: Local / On-Prem Deployment (Default & Recommended for Exam/Testing)

If you are running the project locally without AWS:

1. **Bypass Cloud Provisioning:** Skip running the commands in this directory entirely.
2. **Local Kubernetes Setup:** Deploy directly to your local cluster using the provided Kubernetes manifests:
   ```bash
   kubectl apply -f kubernetes/

```

3. **Local Pipeline Execution:** Jenkins and local security scanners (Bandit, Semgrep, Trivy, OPA) will execute without needing cloud API keys.



---

### Option B: AWS Cloud Provisioning (Optional Integration)

If you wish to demonstrate full AWS Cloud Security integration (CloudTrail, GuardDuty, Security Hub, KMS, and Secrets Manager) as described in the platform architecture:

#### Prerequisites

* [Terraform CLI](https://developer.hashicorp.com/terraform/downloads) (v1.3.0+) installed.
* AWS CLI installed and configured with appropriate IAM credentials (`aws configure`).

#### Steps to Provision Infrastructure

1. Navigate to the terraform directory:
```bash
cd terraform

```


2. Initialize Terraform modules:
```bash
terraform init

```


3. Review the execution plan (Targets AWS Mumbai `ap-south-1`):
```bash
terraform plan

```


4. Apply the configuration to deploy resources:
```bash
terraform apply

```


5. **Clean Up / Destroy Resources:** To avoid cloud costs after testing, remove all created resources:
```bash
terraform destroy

```



---

## 🛠️ Provisioned AWS Resources (When Enabled)

* **AWS KMS (`aws_kms_key`):** Handles encryption key management for data at rest.


* **AWS CloudTrail (`aws_cloudtrail`):** Provides complete API activity auditing.


* **AWS GuardDuty (`aws_guardduty_detector`):** AI-enabled threat detection.


* **AWS Security Hub (`aws_securityhub_account`):** Centralized dashboard for cloud compliance.


* **AWS Secrets Manager (`aws_secretsmanager_secret`):** Secure storage for API tokens and LLM credentials.


* **AWS IAM (`aws_iam_role`):** Role with least-privilege execution access for CI/CD.



```

```
