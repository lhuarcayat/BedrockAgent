#### SQS ####
module "extraction_queue" {
  source = "terraform-aws-modules/sqs/aws"

  name                       = "${var.project_prefix}-extraction-queue"
  visibility_timeout_seconds = 960
}

module "fallback_queue" {
  source = "terraform-aws-modules/sqs/aws"

  name                       = "${var.project_prefix}-fallback-queue"
  visibility_timeout_seconds = 960

}

resource "aws_lambda_event_source_mapping" "extraction" {
  function_name    = module.extraction_scoring_lambda.lambda_function_name
  event_source_arn = module.extraction_queue.queue_arn
  batch_size       = 10 # tune as needed
  depends_on = [
    module.extraction_scoring_lambda.lambda_function_arn
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
  environment_variables = {
    S3_ORIGIN_BUCKET = module.filling_desk_bucket.s3_bucket_id
    EXTRACTION_SQS   = module.extraction_queue.queue_url
    BEDROCK_MODEL    = var.bedrock_model
    FALLBACK_MODEL   = var.fallback_model
    REGION           = var.aws_region
  }
  policy_statements = local.lambda_policy_statements
}

module "extraction_scoring_lambda" {
  source         = "./modules/lambda-wrapper"
  source_path    = "${path.module}/../functions/extraction-scoring/src"
  shared_folder  = "${path.module}/../functions/shared"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name  = "${var.stage_name}-extraction-scoring"
  handler        = "index.handler"
  environment_variables = {
    S3_ORIGIN_BUCKET   = module.filling_desk_bucket.s3_bucket_id
    FALLBACK_SQS       = module.fallback_queue.queue_url
    DESTINATION_BUCKET = module.json-evaluation-results-bucket.s3_bucket_id
    BEDROCK_MODEL      = var.bedrock_model
    FALLBACK_MODEL     = var.fallback_model
    REGION             = var.aws_region
    FOLDER_PREFIX      = var.project_prefix
  }
  policy_statements = local.lambda_policy_statements
  allowed_triggers = {
    sqs_extraction_trigger = {
      principal  = "sqs.amazonaws.com"
      source_arn = module.extraction_queue.queue_arn
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
  for_each = toset(local.folder_suffixes)
  bucket   = module.json-evaluation-results-bucket.s3_bucket_id
  key      = "${var.project_prefix}/${each.value}/"
  depends_on = [
    module.json-evaluation-results-bucket
  ]
}

resource "aws_lambda_permission" "allow_bucket_invoke" {
  statement_id  = "${var.project_prefix}-AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = module.classification_lambda.lambda_function_name
  principal     = "s3.amazonaws.com"
  source_arn    = module.filling_desk_bucket.s3_bucket_arn
}

resource "aws_s3_bucket_notification" "on_upload_file" {
  bucket = module.filling_desk_bucket.s3_bucket_id
  depends_on = [
    aws_lambda_permission.allow_bucket_invoke,
    aws_s3_object.desk_folders
  ]
  dynamic "lambda_function" {
    for_each = local.folder_suffixes
    content {
      events              = ["s3:ObjectCreated:*"]
      id                  = "desk-${lambda_function.value}"
      filter_prefix       = "${var.project_prefix}/${lambda_function.value}/"
      lambda_function_arn = module.classification_lambda.lambda_function_arn
    }

  }
}
