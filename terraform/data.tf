data "aws_caller_identity" "current" {}
data "aws_s3_bucket" "par_servicios_bucket" {
  bucket = "applying-par-textract"
}