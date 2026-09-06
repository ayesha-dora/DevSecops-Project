# VPC Outputs
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "vpc_cidr" {
  value       = aws_vpc.main.cidr_block
  description = "VPC CIDR block"
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "IDs of public subnets"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "IDs of private subnets"
}

# EKS Outputs
output "eks_cluster_name" {
  value       = aws_eks_cluster.devsecops.name
  description = "EKS cluster name"
}

output "eks_cluster_arn" {
  value       = aws_eks_cluster.devsecops.arn
  description = "EKS cluster ARN"
}

output "eks_cluster_endpoint" {
  value       = aws_eks_cluster.devsecops.endpoint
  description = "EKS cluster API endpoint"
}

output "eks_cluster_version" {
  value       = aws_eks_cluster.devsecops.version
  description = "EKS cluster Kubernetes version"
}

# ECR Outputs
output "ecr_repository_url" {
  value       = aws_ecr_repository.app.repository_url
  description = "URL of the ECR repository for pushing Docker images"
}

output "ecr_repository_name" {
  value       = aws_ecr_repository.app.name
  description = "Name of the ECR repository"
}

# IAM Outputs
output "eks_cluster_role_arn" {
  value       = aws_iam_role.eks_cluster_role.arn
  description = "ARN of the EKS cluster IAM role"
}

output "eks_node_role_arn" {
  value       = aws_iam_role.eks_node_role.arn
  description = "ARN of the EKS node IAM role"
}

# Security & Secrets
output "llm_api_key_secret_arn" {
  value       = aws_secretsmanager_secret.llm_api_key.arn
  description = "ARN of the LLM API key secret in Secrets Manager"
}

output "aws_region" {
  value       = var.aws_region
  description = "AWS Region for deployment"
}
