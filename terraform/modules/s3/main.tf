resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_prefix}-raw-bucket"

  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-raw-bucket" }
  )
}

resource "aws_s3_bucket" "processed" {
  bucket = "${var.project_prefix}-processed-bucket"

  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-processed-bucket" }
  )
}

resource "aws_s3_object" "folder" {
  for_each = toset(["CERL", "CECRL", "RUT", "RUB", "ACC"])
  bucket = aws_s3_bucket.raw.id
  key    = "${each.value}/"
  source = "/dev/null"
}
