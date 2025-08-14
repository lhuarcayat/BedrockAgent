locals {
  account_id = data.aws_caller_identity.current.account_id
  folder_suffixes = [
    "CERL",
    "CECRL",
    "RUT",
    "RUB",
    "ACC"
  ]
  source_bucket_id  = data.aws_s3_bucket.par_servicios_bucket.id
  source_bucket_arn = data.aws_s3_bucket.par_servicios_bucket.arn
  lambda_policy_statements = {
    s3_access = {
      effect  = "Allow"
      actions = ["s3:*"]
      resources = [
        module.filling_desk_bucket.s3_bucket_arn,
        "${module.filling_desk_bucket.s3_bucket_arn}/*",
        module.json-evaluation-results-bucket.s3_bucket_arn,
        "${module.json-evaluation-results-bucket.s3_bucket_arn}/*"
      ]
    }
    sqs_access = {
      effect    = "Allow"
      actions   = ["sqs:*"]
      resources = ["*"]
    }
    bedrock_access = {
      effect    = "Allow"
      actions   = ["bedrock:*"]
      resources = ["*"]
    }
    dynamodb_access = {
      effect    = "Allow"
      actions   = [
        "dynamodb:PutItem",
        "dynamodb:GetItem", 
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ]
      resources = ["arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/${var.project_prefix}-${var.stage_name}-idempotency"]
    }
  }


}
