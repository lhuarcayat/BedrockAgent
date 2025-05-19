resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_prefix}-${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-${var.function_name}-role" }
  )
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${var.project_prefix}-${var.function_name}-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "textract:AnalyzeDocument",
          "textract:StartDocumentAnalysis"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "main" {
  function_name = "${var.project_prefix}-${var.function_name}"
  handler       = var.handler
  runtime       = var.runtime
  role          = aws_iam_role.lambda_exec.arn

  environment {
    variables = var.environment
  }

  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-${var.function_name}" }
  )

  # Source code will be uploaded separately
  filename         = "${path.module}/../../functions/${var.function_name}/src/lambda_function.zip"
  source_code_hash = filebase64sha256("${path.module}/../../functions/${var.function_name}/src/lambda_function.zip")
}
