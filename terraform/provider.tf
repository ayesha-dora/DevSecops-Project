terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Configured for AWS Mumbai Region (ap-south-1)
provider "aws" {
  region = "ap-south-1"

  default_tags {
    tags = {
      Environment = "Exam-DevSecOps"
      Project     = "AI-Augmented-CI-CD"
      ManagedBy   = "Terraform"
    }
  }
}
