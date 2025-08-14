variable "project_prefix" {
  type        = string
  description = "Project prefix for resource naming"
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

variable "exclude_files" {
  type        = list(string)
  description = "List of files to be excluded from deployment"
  default     = [
    "tests",
    "makefile",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "Dockerfile",
    ".gitignore",
    ".gitattributes",
    ".git/",
    "!test_*.py"
    ]
}

variable "tags" {
  type        = list(string)
  description = "List of tags to apply to resources"
  default     = ["par-servicios", "agents-bedrock"]
}

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "source_path" {
  description = "Source code path for the Lambda"
  type        = any
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "policy_statements" {
  description = "IAM policy statements for Lambda permissions"
  type        = any
  default     = {}
}

variable "publish" {
  description = "Whether to publish a new Lambda version on changes"
  type        = bool
  default     = true
}

variable "allowed_triggers" {
  description = "Event sources that trigger the Lambda"
  type        = any
  default     = {}
}

variable "cloudwatch_logs_retention_in_days" {
  description = "CloudWatch logs retention period for Lambda function"
  type        = number
  default     = 90
}

variable "memory_size" {
  description = "Memory size for the Lambda function (overrides default if set)"
  type        = number
  default     = null
}

variable "timeout" {
  description = "Timeout in seconds for the Lambda function (overrides default if set)"
  type        = number
  default     = null
}

variable "pip_requirements" {
  type        = bool
  description = "if have to a requirements.txt file for build"
  default     = false
}

variable "shared_folder" {
  type        = string
  description = "List of comands to execute"
  default     = ""
}