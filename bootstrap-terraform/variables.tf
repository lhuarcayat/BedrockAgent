# Bootstrap variables
variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "stage_name" {
  description = "Stage name (e.g. dev, prod)"
  type        = string
}

variable "service_name" {
  description = "Service name"
  type        = string
}
