# Backend configuration for bootstrap
# Initially, this will use local state
# After the first apply, you can migrate to S3

terraform {
  # backend "s3" {}
  backend "local" {}
}
