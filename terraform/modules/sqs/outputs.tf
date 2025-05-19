output "extraction_queue_url" {
  value = aws_sqs_queue.extraction.url
}

output "extraction_queue_arn" {
  value = aws_sqs_queue.extraction.arn
}

output "fallback_queue_url" {
  value = aws_sqs_queue.fallback.url
}

output "fallback_queue_arn" {
  value = aws_sqs_queue.fallback.arn
}
