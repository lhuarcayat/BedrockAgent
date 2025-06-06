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
  region = "us-east-2"

  default_tags {
    tags = {
      Project   = var.service_name
      CostComponent = var.cost_component
      Environment = var.stage_name
    }
  }
}
