variable "project_prefix" {
  type        = string
  description = "Project prefix for resource naming"
}

variable "tags" {
  type        = list(string)
  description = "List of tags to apply to resources"
  default     = ["par-servicios", "agents-bedrock"]
}
