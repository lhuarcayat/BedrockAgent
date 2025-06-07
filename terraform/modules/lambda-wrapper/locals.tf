locals {
  default_memory_size = 1024
  default_timeout     = 6
  lambda_source_path = [
    {
      path             = var.source_path
      pip_requirements = var.pip_requirements
      patterns         = var.exclude_files
      commands = [
        "rm -rf ../.build/",
        "mkdir -p ../.build",
        "uv pip install --no-compile --target=../.build --requirement=requirements.txt",
        "cp -R \"${abspath(var.source_path)}/.\" ../.build/",
        "cp -R \"${abspath(var.shared_folder)}\" ../.build/shared",
        ":zip ../.build",
      ]
    }
  ]
}
