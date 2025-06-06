locals {
  account_id = data.aws_caller_identity.current.account_id
  folder_suffixes = [
    "CERL",
    "CECRL",
    "RUT",
    "RUB",
    "ACC"
  ]
  source_bucket_id = data.aws_s3_bucket.par_servicios_bucket.id
  source_bucket_arn = data.aws_s3_bucket.par_servicios_bucket.arn

}