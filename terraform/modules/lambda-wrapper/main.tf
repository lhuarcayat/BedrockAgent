module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 7.0"

  function_name = "${var.project_prefix}-${var.function_name}"
  handler       = var.handler
  runtime       = var.runtime

  # Use the processed source_path configuration
  source_path     = local.lambda_source_path
  # create_package  = false
  # local_existing_package = archive_file.package

  environment_variables             = var.environment_variables
  attach_policy_statements          = var.policy_statements != null ? true : false
  policy_statements                 = var.policy_statements
  publish                           = var.publish
  allowed_triggers                  = var.allowed_triggers
  cloudwatch_logs_retention_in_days = var.cloudwatch_logs_retention_in_days

  memory_size = var.memory_size != null ? var.memory_size : local.default_memory_size
  timeout     = var.timeout != null ? var.timeout : local.default_timeout
}
