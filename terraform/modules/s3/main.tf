module "s3_bucket" {
  source = "terraform-aws-modules/s3-bucket/aws"
  bucket = var.bucket_name
  acl    = var.acl

  control_object_ownership = var.control_object_ownership
  object_ownership         = var.object_ownership

  versioning = {
    enabled = var.is_versioned
  }
  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = var.bucket_name }
  )
}

# resource "aws_s3_bucket" "raw" {
#   bucket = "${var.project_prefix}-raw-bucket"

#   tags = merge(
#     { for tag in var.tags : tag => true },
#     { Name = "${var.project_prefix}-raw-bucket" }
#   )
# }

# resource "aws_s3_bucket" "processed" {
#   bucket = "${var.project_prefix}-processed-bucket"

#   tags = merge(
#     { for tag in var.tags : tag => true },
#     { Name = "${var.project_prefix}-processed-bucket" }
#   )
# }

# resource "aws_s3_object" "folder" {
#   for_each = toset(["CERL", "CECRL", "RUT", "RUB", "ACC"])
#   bucket = aws_s3_bucket.raw.id
#   key    = "${each.value}/"
#   source = "/dev/null"
# }
