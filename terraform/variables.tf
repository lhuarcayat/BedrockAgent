variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "stage_name" {
  description = "Stage name (e.g. dev, prod)"
  type        = string
  default     = "dev"
}

variable "service_name" {
  description = "Service name"
  type        = string
  default     = "par-servicios-poc-bedrock"
}

variable "project_prefix" {
  description = "Project prefix (e.g. mycompany-"
  type        = string
  default     = "par-servicios-poc"
}