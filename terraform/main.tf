#### DYNAMODB ####
module "idempotency_table" {
  source = "terraform-aws-modules/dynamodb-table/aws"

  name         = "${var.project_prefix}-${var.stage_name}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attributes = [
    {
      name = "pk"
      type = "S"
    }
  ]

  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = {
    Environment = var.stage_name
    Project     = var.project_prefix
    Purpose     = "idempotency-locking"
  }
}

module "manual_review_table" {
  source = "terraform-aws-modules/dynamodb-table/aws"

  name         = "${var.project_prefix}-${var.stage_name}-manual-review"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attributes = [
    {
      name = "pk"
      type = "S"
    },
    {
      name = "sk"
      type = "S"
    },
    {
      name = "gsi1pk"
      type = "S"
    },
    {
      name = "gsi1sk"
      type = "S"
    }
  ]

  global_secondary_indexes = [
    {
      name            = "DocumentIndex"
      hash_key        = "gsi1pk"
      range_key       = "gsi1sk"
      projection_type = "ALL"
    }
  ]

  ttl_enabled        = true
  ttl_attribute_name = "ttl"

  tags = {
    Environment = var.stage_name
    Project     = var.project_prefix
    Purpose     = "manual-review-tracking"
  }
}

#### SQS ####
module "classification_queue" {
  source = "terraform-aws-modules/sqs/aws"

  name                       = "${var.project_prefix}-${var.stage_name}-classification-queue"
  visibility_timeout_seconds = 960
  create_dlq                 = true
  dlq_name                  = "${var.project_prefix}-${var.stage_name}-classification-dlq"
  redrive_policy = {
    maxReceiveCount = 10
  }
  create_queue_policy = true
  queue_policy_statements = {
    s3_publish = {
      sid    = "AllowS3Publish"
      effect = "Allow"
      principals = [
        {
          type        = "Service"
          identifiers = ["s3.amazonaws.com"]
        }
      ]
      actions   = ["sqs:SendMessage"]
      resources = ["arn:aws:sqs:${var.aws_region}:${local.account_id}:${var.project_prefix}-${var.stage_name}-classification-queue"]
      conditions = [
        {
          test     = "ArnEquals"
          variable = "aws:SourceArn"
          values   = [module.filling_desk_bucket.s3_bucket_arn]
        }
      ]
    }
  }
}

module "extraction_queue" {
  source = "terraform-aws-modules/sqs/aws"

  name                       = "${var.project_prefix}-${var.stage_name}-extraction-queue"
  visibility_timeout_seconds = 960
}

module "fallback_queue" {
  source = "terraform-aws-modules/sqs/aws"

  name                       = "${var.project_prefix}-${var.stage_name}-fallback-queue"
  visibility_timeout_seconds = 960

}

resource "aws_lambda_event_source_mapping" "classification" {
  function_name                           = module.classification_lambda.lambda_function_name
  event_source_arn                        = module.classification_queue.queue_arn
  batch_size                              = 3 # items to acumulate before invoking the function
  maximum_batching_window_in_seconds      = 5 # time to wait for more messages before invoking the function
  function_response_types                 = ["ReportBatchItemFailures"]
  depends_on = [
    module.classification_lambda.lambda_function_arn
  ]
}

resource "aws_lambda_event_source_mapping" "extraction" {
  function_name                      = module.extraction_scoring_lambda.lambda_function_name
  event_source_arn                   = module.extraction_queue.queue_arn
  batch_size                         = 3  # items to accumulate before invoking the function
  maximum_batching_window_in_seconds = 5  # time to wait for more messages before invoking the function
  depends_on = [
    module.extraction_scoring_lambda.lambda_function_arn
  ]
}

resource "aws_lambda_event_source_mapping" "fallback" {
  function_name                      = module.fallback_processing_lambda.lambda_function_name
  event_source_arn                   = module.fallback_queue.queue_arn
  batch_size                         = 3  # items to accumulate before invoking the function
  maximum_batching_window_in_seconds = 5  # time to wait for more messages before invoking the function
  function_response_types            = ["ReportBatchItemFailures"]
  depends_on = [
    module.fallback_processing_lambda.lambda_function_arn
  ]
}

#### LAMBA ####
module "classification_lambda" {
  source         = "./modules/lambda-wrapper"
  source_path    = "${path.module}/../functions/classification/src"
  shared_folder  = "${path.module}/../functions/shared"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name  = "${var.stage_name}-classification"
  handler        = "index.handler"
  pip_requirements = true
  environment_variables = {
    S3_ORIGIN_BUCKET = module.filling_desk_bucket.s3_bucket_id
    DESTINATION_BUCKET = module.json-evaluation-results-bucket.s3_bucket_id
    EXTRACTION_SQS   = module.extraction_queue.queue_url
    BEDROCK_MODEL    = var.bedrock_model
    FALLBACK_MODEL   = var.fallback_model
    REGION           = var.aws_region
    FOLDER_PREFIX    = var.project_prefix
    IDEMPOTENCY_TABLE = module.idempotency_table.dynamodb_table_id
    BEDROCK_RETRY_ATTEMPTS = "8"
    INTER_CALL_DELAY = "5.0"
    BATCH_PROCESSING_DELAY = "2.0"
  }
  policy_statements = local.lambda_policy_statements
  allowed_triggers = {
    sqs_classification_trigger = {
      principal  = "sqs.amazonaws.com"
      source_arn = module.classification_queue.queue_arn
    }
  }
}

module "extraction_scoring_lambda" {
  source         = "./modules/lambda-wrapper"
  source_path    = "${path.module}/../functions/extraction-scoring/src"
  shared_folder  = "${path.module}/../functions/shared"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name  = "${var.stage_name}-extraction-scoring"
  handler        = "index.handler"
  pip_requirements = true
  environment_variables = {
    S3_ORIGIN_BUCKET   = module.filling_desk_bucket.s3_bucket_id
    FALLBACK_SQS       = module.fallback_queue.queue_url
    DESTINATION_BUCKET = module.json-evaluation-results-bucket.s3_bucket_id
    BEDROCK_MODEL      = var.bedrock_model
    FALLBACK_MODEL     = var.fallback_model
    REGION             = var.aws_region
    FOLDER_PREFIX      = var.project_prefix
    BEDROCK_RETRY_ATTEMPTS = "8"
    INTER_CALL_DELAY = "5.0"
    BATCH_PROCESSING_DELAY = "5.0"
  }
  policy_statements = local.lambda_policy_statements
  allowed_triggers = {
    sqs_extraction_trigger = {
      principal  = "sqs.amazonaws.com"
      source_arn = module.extraction_queue.queue_arn
    }
  }
}

module "fallback_processing_lambda" {
  source         = "./modules/lambda-wrapper"
  source_path    = "${path.module}/../functions/fallback-processing/src"
  shared_folder  = "${path.module}/../functions/shared"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name  = "${var.stage_name}-fallback-processing"
  handler        = "index.handler"
  pip_requirements = true
  environment_variables = {
    MANUAL_REVIEW_TABLE = module.manual_review_table.dynamodb_table_id
    BEDROCK_MODEL       = var.bedrock_model
    DESTINATION_BUCKET  = module.json-evaluation-results-bucket.s3_bucket_id
    FALLBACK_MODEL      = var.fallback_model
    REGION              = var.aws_region
    FOLDER_PREFIX       = var.project_prefix
    S3_ORIGIN_BUCKET    = module.filling_desk_bucket.s3_bucket_id
  }
  policy_statements = local.lambda_policy_statements
  allowed_triggers = {
    sqs_fallback_trigger = {
      principal  = "sqs.amazonaws.com"
      source_arn = module.fallback_queue.queue_arn
    }
  }
}

#### S3 ####

module "filling_desk_bucket" {
  source         = "./modules/s3"
  bucket_name    = "${var.project_prefix}-${var.stage_name}-filling-desk"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  tags           = []
}

module "json-evaluation-results-bucket" {
  source         = "./modules/s3"
  bucket_name    = "${var.project_prefix}-${var.stage_name}-json-evaluation-results"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  tags           = []
}
resource "aws_s3_object" "desk_folders" {
  for_each = toset(local.folder_suffixes)
  bucket   = module.filling_desk_bucket.s3_bucket_id
  key      = "${var.project_prefix}/${each.value}/"
  depends_on = [
    module.filling_desk_bucket
  ]
}

resource "aws_s3_object" "destination_folders" {
  for_each = { for folder in local.destination_folder_structure : folder.name => folder }
  bucket   = module.json-evaluation-results-bucket.s3_bucket_id
  key      = each.value.key
  depends_on = [
    module.json-evaluation-results-bucket
  ]
}

resource "aws_s3_bucket_notification" "on_upload_file" {
  bucket = module.filling_desk_bucket.s3_bucket_id
  depends_on = [
    aws_s3_object.desk_folders
  ]
  dynamic "queue" {
    for_each = local.folder_suffixes
    content {
      events        = ["s3:ObjectCreated:*"]
      id            = "desk-${queue.value}"
      filter_prefix = "${var.project_prefix}/${queue.value}/"
      filter_suffix = ".pdf"
      queue_arn     = module.classification_queue.queue_arn
    }
  }
}
