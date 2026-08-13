output "metrics_function_name" {
  description = "Name of the metrics collector Lambda function."
  value       = aws_lambda_function.metrics.function_name
}

output "logs_function_name" {
  description = "Name of the logs collector Lambda function."
  value       = aws_lambda_function.logs.function_name
}

output "checkpoint_bucket" {
  description = "S3 bucket holding the logs collector's dedup checkpoint."
  value       = aws_s3_bucket.checkpoint.id
}

output "checkpoint_uri" {
  description = "Full s3:// URI of the logs checkpoint object."
  value       = "s3://${aws_s3_bucket.checkpoint.id}/${local.checkpoint_key}"
}

output "dlq_url" {
  description = "URL of the dead-letter queue (null if disabled)."
  value       = var.enable_dlq ? aws_sqs_queue.dlq[0].url : null
}
