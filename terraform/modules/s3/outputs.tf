output "s3_bucket_arn" {
  value = module.s3_bucket.s3_bucket_arn
}

output "s3_bucket_bucket_domain_name" {
  value = module.s3_bucket.s3_bucket_bucket_domain_name
}

output "s3_bucket_id" {
  description = "The name of the bucket"
  value = module.s3_bucket.s3_bucket_id
}

output "s3_bucket_region" {
  description = "The AWS region this bucket resides in"
  value = module.s3_bucket.s3_bucket_region
}

output "s3_directory_bucket_arn" {
  value = module.s3_bucket.s3_directory_bucket_arn
}

output "s3_directory_bucket_name" {
  value = module.s3_bucket.s3_directory_bucket_name
}