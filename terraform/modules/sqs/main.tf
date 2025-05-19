resource "aws_sqs_queue" "extraction" {
  name = "${var.project_prefix}-extraction-queue"
  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-extraction-queue" }
  )
}

resource "aws_sqs_queue" "fallback" {
  name = "${var.project_prefix}-fallback-queue"
  tags = merge(
    { for tag in var.tags : tag => true },
    { Name = "${var.project_prefix}-fallback-queue" }
  )
}
