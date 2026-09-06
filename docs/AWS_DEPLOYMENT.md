# AWS Deployment Guide

## Overview

This guide provides step-by-step instructions to deploy the DevSecOps application to AWS using:
- **Amazon EKS** (Elastic Kubernetes Service) for container orchestration
- **Amazon ECR** (Elastic Container Registry) for Docker image storage
- **Terraform** for infrastructure as code
- **Helm** for Kubernetes application management

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI configured with credentials
- Terraform 1.0+
- kubectl 1.27+
- Helm 3+
- Docker (for building images)
- Git

## Architecture

```
Internet
   ↓
AWS Load Balancer
   ↓
EKS Ingress Controller
   ↓
Kubernetes Service
   ↓
Application Pods (EKS nodes)
   ↓
ECR (Docker images)
   ↓
CloudWatch (Logs)
```

## Deployment Steps

### Step 1: Configure AWS Credentials

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

### Step 2: Initialize Terraform

```bash
cd terraform
terraform init
```

### Step 3: Review and Customize Variables

Edit `terraform/terraform.tfvars` or pass variables:

```bash
terraform plan \
  -var="aws_region=us-east-1" \
  -var="environment=dev" \
  -var="node_desired_size=2" \
  -var="node_max_size=4"
```

### Step 4: Deploy AWS Infrastructure

```bash
terraform plan    # Review changes
terraform apply   # Deploy to AWS
```

**Expected output**: VPC, EKS cluster, ECR repository, security groups, IAM roles

### Step 5: Configure kubectl

```bash
aws eks update-kubeconfig \
  --region us-east-1 \
  --name devsecops-cluster

# Verify
kubectl get nodes
```

### Step 6: Authenticate to ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $(aws ecr describe-repositories --region us-east-1 --query 'repositories[0].repositoryUri' --output text | cut -d/ -f1)
```

### Step 7: Build and Push Docker Image

```bash
# Build image
docker build -t devsecops-app:latest -f app/Dockerfile .

# Tag for ECR
docker tag devsecops-app:latest \
  <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devsecops-app:latest

# Push to ECR
docker push \
  <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devsecops-app:latest
```

### Step 8: Update Kubernetes Manifests

Update image in `kubernetes/deployment.yaml`:

```yaml
image: <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devsecops-app:latest
```

### Step 9: Deploy Application to EKS

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Deploy using Helm
helm install devsecops-app ./helm/devsecops-app \
  --namespace devsecops \
  --values helm/devsecops-app/values.yaml \
  --set image.repository=<AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devsecops-app \
  --set image.tag=latest

# Or deploy raw manifests
kubectl apply -f kubernetes/ --namespace devsecops
```

### Step 10: Verify Deployment

```bash
# Check pods
kubectl get pods --namespace devsecops

# Check services
kubectl get svc --namespace devsecops

# Check ingress
kubectl get ingress --namespace devsecops

# Logs
kubectl logs -f deployment/devsecops-app -n devsecops
```

### Step 11: Access Application

```bash
# Get ALB DNS
kubectl get ingress -n devsecops -o wide

# Test
curl http://<ALB_DNS>/health
curl http://<ALB_DNS>/users
```

## CI/CD Integration with Jenkins

### Jenkins AWS Credentials

Add to Jenkins:
1. AWS Access Key ID
2. AWS Secret Access Key
3. Docker Registry Credentials (ECR)

### Jenkins Pipeline Stages for AWS

```groovy
stage('Push to ECR') {
  steps {
    sh '''
      aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
      docker build -t devsecops-app:${BUILD_NUMBER} .
      docker tag devsecops-app:${BUILD_NUMBER} $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/devsecops-app:${BUILD_NUMBER}
      docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/devsecops-app:${BUILD_NUMBER}
    '''
  }
}

stage('Deploy to EKS') {
  steps {
    sh '''
      aws eks update-kubeconfig --region us-east-1 --name devsecops-cluster
      helm upgrade --install devsecops-app ./helm/devsecops-app \
        --namespace devsecops \
        --set image.tag=${BUILD_NUMBER}
    '''
  }
}
```

## Monitoring

### CloudWatch Logs

```bash
# View EKS cluster logs
aws logs tail /aws/eks/devsecops-cluster/cluster --follow
```

### Prometheus (In-cluster)

```bash
kubectl port-forward -n devsecops svc/prometheus 9090:9090
# Access at http://localhost:9090
```

### Grafana (In-cluster)

```bash
kubectl port-forward -n devsecops svc/grafana 3000:3000
# Access at http://localhost:3000
```

## Cleanup

### Destroy AWS Infrastructure

```bash
# Delete Kubernetes resources first
kubectl delete namespace devsecops

# Destroy Terraform infrastructure
cd terraform
terraform destroy
```

## Cost Estimation

**Monthly Costs (Rough Estimates)**:
- EKS Control Plane: $73
- EC2 Nodes (t3.medium x 2): ~$30-60
- Data Transfer: $5-15
- ECR Storage: $1-5

**Total: ~$110-150/month** for development environment

## Troubleshooting

### Pod not starting

```bash
kubectl describe pod -n devsecops
kubectl logs pod_name -n devsecops
```

### ECR authentication failed

```bash
# Re-authenticate
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
```

### Ingress not accessible

```bash
# Check ingress controller
kubectl get pods -n kube-system | grep aws-load-balancer-controller

# Check service
kubectl get svc -n devsecops
```

## References

- [AWS EKS Documentation](https://docs.aws.amazon.com/eks/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)

