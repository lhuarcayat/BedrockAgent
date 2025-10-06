locals {
  account_id = data.aws_caller_identity.current.account_id
  folder_suffixes = [
    "CERL",
    "CECRL",
    "RUT",
    "RUB",
    "ACC"
  ]
  destination_folder_structure = flatten([
    for process_type in ["classification", "extraction"] : [
      for category in local.folder_suffixes : {
        key = "${var.project_prefix}/${process_type}/${category}/"
        name = "${process_type}_${category}"
      }
    ]
  ])
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
    textract_access = {
      effect    = "Allow"
      actions   = [
        "textract:StartDocumentTextDetection",
        "textract:GetDocumentTextDetection",
        "textract:StartDocumentAnalysis",
        "textract:GetDocumentAnalysis"
      ]
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
      resources = [
        "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/${var.project_prefix}-${var.stage_name}-idempotency",
        "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/${var.project_prefix}-${var.stage_name}-manual-review"
      ]
    }
  }
}
