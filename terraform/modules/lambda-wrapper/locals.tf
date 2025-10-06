locals {
  default_memory_size = 1024
  default_timeout     = 900
  
  # Convert exclude patterns to include patterns for terraform-aws-lambda
  # terraform-aws-lambda uses regex patterns where ".*" means include all
  # and "!pattern" means exclude
  # NOTE: requirements.txt is needed during build but excluded from final ZIP
  exclude_patterns_filtered = [
    for pattern in var.exclude_files : 
    pattern if pattern != "requirements.txt"  # Allow requirements.txt during build
  ]
  
  include_patterns = concat(
    [".*"],  # Include everything by default
    [for pattern in local.exclude_patterns_filtered : "!${pattern}"]  # Convert to exclusions
  )
  
  # Base source path configuration (always included)
  base_source_config = {
    path             = var.source_path
    pip_requirements = var.pip_requirements
    patterns         = local.include_patterns
  }
  
  # Shared folder configuration (conditionally included)
  shared_config = var.shared_folder != "" ? [{
    path          = var.shared_folder
    prefix_in_zip = "shared"
    patterns      = [".*"]  # Include everything from shared folder
  }] : []
  
  # Use terraform-aws-lambda's built-in packaging with conditional shared folder
  lambda_source_path = concat([local.base_source_config], local.shared_config)
}
