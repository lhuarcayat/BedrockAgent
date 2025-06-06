#### SQS ####
module "sqs" {
  source       = "./modules/sqs"
  project_prefix = "${var.project_prefix}-extraction-sqs"
}

#### LAMBA ####
module "classification_lambda" {
  source       = "./modules/lambda-wrapper"
  source_path  = "${path.module}/../functions/classification/src"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name = "${var.stage_name}-classification"
  handler      = "index.handler"
  environment = {
    # S3_BUCKET      = module.s3.raw_bucket_name
    EXTRACTION_SQS = module.sqs.extraction_queue_url
  }
}

module "extraction_scoring_lambda" {
  source       = "./modules/lambda-wrapper"
  source_path  = "${path.module}/../functions/extraction-scoring/src"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  function_name = "${var.stage_name}-extraction-scoring"
  handler      = "index.handler"
  environment = {
    # S3_BUCKET    = module.s3.processed_bucket_name
    FALLBACK_SQS = module.sqs.fallback_queue_url
  }
}

#### S3 ####

module "filling_desk_bucket" {
  source = "./modules/s3"
  bucket_name = "${var.project_prefix}-${var.stage_name}-filling-desk"
  project_prefix = "${var.project_prefix}-${local.account_id}"
  tags = []
}
resource "aws_s3_object" "desk_folders" {
  for_each = toset(local.folder_suffixes)
  bucket   = module.filling_desk_bucket.s3_bucket_id
  key      = "${var.project_prefix}/${each.value}/"
  depends_on = [
    module.filling_desk_bucket
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