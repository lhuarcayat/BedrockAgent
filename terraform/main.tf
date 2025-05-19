module "s3" {
  source       = "./modules/s3"
  project_prefix = "par-servicios-poc"
  tags         = ["par-servicios", "agents-bedrock"]
}

module "sqs" {
  source       = "./modules/sqs"
  project_prefix = "par-servicios-poc"
  tags         = ["par-servicios", "agents-bedrock"]
}

module "classification_lambda" {
  source       = "./modules/lambda-wrapper"
  project_prefix = "par-servicios-poc"
  function_name = "classification"
  handler      = "src/lambda_function.lambda_handler"
  runtime      = "python3.12"
  environment = {
    S3_BUCKET      = module.s3.raw_bucket_name
    EXTRACTION_SQS = module.sqs.extraction_queue_url
  }
}

module "extraction_scoring_lambda" {
  source       = "./modules/lambda-wrapper"
  project_prefix = "par-servicios-poc"
  function_name = "extraction-scoring"
  handler      = "src/lambda_function.lambda_handler"
  runtime      = "python3.12"
  environment = {
    S3_BUCKET    = module.s3.processed_bucket_name
    FALLBACK_SQS = module.sqs.fallback_queue_url
  }
}
