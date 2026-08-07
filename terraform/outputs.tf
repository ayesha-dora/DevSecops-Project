output "aws_region" {
  value       = "ap-south-1 (Mumbai)"
  description = "Deployed AWS Region"
}

output "kms_key_arn" {
  value       = aws_kms_key.devsecops_key.arn
  description = "ARN of KMS Key used for pipeline data encryption"
}

output "guardduty_detector_id" {
  value       = aws_guardduty_detector.main.id
  description = "GuardDuty Detector ID"
}

output "secrets_manager_arn" {
  value       = aws_secretsmanager_secret.llm_api_key.arn
  description = "Secrets Manager ARN for LLM Credentials"
}
