terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = ">= 1.5.0"
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = var.service_name
      Component = "agents-bedrock"
      Environment = var.stage_name
    }
  }
}
