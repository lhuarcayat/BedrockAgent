variable "project_prefix" {
  type        = string
  description = "Project prefix for resource naming"
}

variable "function_name" {
  type        = string
  description = "Name of the Lambda function"
}

variable "handler" {
  type        = string
  description = "Lambda handler entry point"
}

variable "runtime" {
  type        = string
  description = "Lambda runtime environment"
  default     = "python3.12"
}

variable "environment" {
  type        = map(string)
  description = "Environment variables for Lambda function"
  default     = {}
}

variable "tags" {
  type        = list(string)
  description = "List of tags to apply to resources"
  default     = ["par-servicios", "agents-bedrock"]
}
