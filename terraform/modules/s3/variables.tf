variable "project_prefix" {
  type        = string
  description = "Project prefix for resource naming"
}

variable "tags" {
  type        = list(string)
  description = "List of tags to apply to resources"
}

variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket to create"
}

variable "acl" {
  type        = string
  description = "ACL to apply to the bucket"
  default     = "private"
}

variable "is_versioned" {
  type        = bool
  description = "Enable versioning on the bucket"
  default     = true
}

variable "control_object_ownership" {
  type        = bool
  description = "Enable object ownership control on the bucket"
  default     = true
}

variable "object_ownership" {
  type        = string
  description = "Object ownership type"
  default     = "ObjectWriter"
}