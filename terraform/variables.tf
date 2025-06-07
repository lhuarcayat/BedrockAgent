variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
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

variable "cost_component" {
  description = "cost identificator"
  type        = string
  default     = "agents-bedrock"
}

variable "bedrock_model" {
  description = "bedrock model"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "fallback_model" {
  description = "fallback model"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-20250514-v1:0"
}