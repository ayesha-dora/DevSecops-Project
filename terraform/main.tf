# 1. KMS Key for Encryption at Rest
resource "aws_kms_key" "devsecops_key" {
  description             = "KMS Key for DevSecOps AI Pipeline Data Encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# 2. S3 Bucket for CloudTrail Logs
resource "aws_s3_bucket" "trail_bucket" {
  bucket        = "devsecops-cloudtrail-logs-mumbai-exam"
  force_destroy = true
}

# 3. AWS CloudTrail (API Audit Logging)
resource "aws_cloudtrail" "main_trail" {
  name                          = "devsecops-audit-trail"
  s3_bucket_name                = aws_s3_bucket.trail_bucket.id
  include_global_service_events = true
  is_multi_region_trail         = false
  kms_key_id                    = aws_kms_key.devsecops_key.arn
}

# 4. AWS GuardDuty (Threat Detection)
resource "aws_guardduty_detector" "main" {
  enable = true
}

# 5. AWS Security Hub (Centralized Security Management)
resource "aws_securityhub_account" "main" {}

# 6. AWS Secrets Manager (For storing LLM API Keys & Vault credentials)
resource "aws_secretsmanager_secret" "llm_api_key" {
  name                    = "devsecops/llm_api_key"
  kms_key_id              = aws_kms_key.devsecops_key.arn
  recovery_window_in_days = 0
}

# 7. IAM Role with Least Privilege Access for Jenkins CI/CD
resource "aws_iam_role" "jenkins_role" {
  name = "devsecops-jenkins-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}
