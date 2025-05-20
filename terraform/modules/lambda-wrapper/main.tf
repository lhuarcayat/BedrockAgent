locals {
  default_memory_size = 1024
  default_timeout     = 6
  default_runtime     = "python3.11"
}

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${var.project_prefix}-${var.function_name}"
  handler       = var.handler
  runtime       = var.runtime != null ? var.runtime : local.default_runtime
  source_path   = var.source_path

  environment_variables            = var.environment_variables
  attach_policy_statements         = var.attach_policy_statements
  policy_statements                = var.policy_statements
  publish                          = var.publish
  allowed_triggers                 = var.allowed_triggers
  cloudwatch_logs_retention_in_days = var.cloudwatch_logs_retention_in_days

  memory_size = var.memory_size != null ? var.memory_size : local.default_memory_size
  timeout     = var.timeout     != null ? var.timeout     : local.default_timeout
}
