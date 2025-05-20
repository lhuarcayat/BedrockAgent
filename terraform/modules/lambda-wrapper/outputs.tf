output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda.lambda_function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda.lambda_function_arn
}
output "lambda_function_invoke_arn" {
  description = "Invoke ARN of the Lambda function"
  value = module.lambda.lambda_function_invoke_arn
}