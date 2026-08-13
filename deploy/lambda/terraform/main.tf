terraform {
  required_version = ">= 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  checkpoint_bucket = var.checkpoint_bucket != "" ? var.checkpoint_bucket : "${var.name_prefix}-checkpoints-${data.aws_caller_identity.current.account_id}"
  checkpoint_key    = var.checkpoint_key
  dlq_arn           = var.enable_dlq ? aws_sqs_queue.dlq[0].arn : null
}

# ---------------------------------------------------------------------------
# Durable checkpoint store for the (stateful) logs collector
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "checkpoint" {
  bucket = local.checkpoint_bucket
}

resource "aws_s3_bucket_versioning" "checkpoint" {
  bucket = aws_s3_bucket.checkpoint.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "checkpoint" {
  bucket                  = aws_s3_bucket.checkpoint.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Optional dead-letter queue for failed scheduled invocations
# ---------------------------------------------------------------------------
resource "aws_sqs_queue" "dlq" {
  count                     = var.enable_dlq ? 1 : 0
  name                      = "${var.name_prefix}-dlq"
  message_retention_seconds = 1209600 # 14 days
}

# ---------------------------------------------------------------------------
# IAM: shared assume-role policy for Lambda
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ----- Metrics function role -----------------------------------------------
resource "aws_iam_role" "metrics" {
  name               = "${var.name_prefix}-metrics-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "metrics_basic" {
  role       = aws_iam_role.metrics.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "metrics_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.metrics_secret_arn]
  }
}

resource "aws_iam_role_policy" "metrics_secret" {
  name   = "read-secret"
  role   = aws_iam_role.metrics.id
  policy = data.aws_iam_policy_document.metrics_secret.json
}

# ----- Logs function role ---------------------------------------------------
resource "aws_iam_role" "logs" {
  name               = "${var.name_prefix}-logs-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "logs_basic" {
  role       = aws_iam_role.logs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "logs_policy" {
  statement {
    sid       = "ReadSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.logs_secret_arn]
  }
  statement {
    sid       = "CheckpointObject"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.checkpoint.arn}/${local.checkpoint_key}"]
  }
  # ListBucket so a GetObject on the not-yet-created checkpoint object returns
  # 404 (NoSuchKey) instead of 403 (AccessDenied) on the very first run.
  statement {
    sid       = "ListCheckpointBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.checkpoint.arn]
  }
}

resource "aws_iam_role_policy" "logs_policy" {
  name   = "logs-access"
  role   = aws_iam_role.logs.id
  policy = data.aws_iam_policy_document.logs_policy.json
}

# ---------------------------------------------------------------------------
# Lambda functions
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "metrics" {
  function_name    = "${var.name_prefix}-metrics"
  role             = aws_iam_role.metrics.arn
  runtime          = var.runtime
  handler          = "mariadb_metrics_collector.lambda_handler"
  filename         = var.metrics_zip
  source_code_hash = filebase64sha256(var.metrics_zip)
  timeout          = var.metrics_timeout
  memory_size      = var.metrics_memory_size

  environment {
    variables = {
      SECRETS_ARN           = var.metrics_secret_arn
      MARIADB_API_URL       = var.mariadb_api_url
      SPLUNK_HEC_URL        = var.splunk_hec_url
      SPLUNK_INDEX          = var.splunk_index_metrics
      SPLUNK_HEC_VERIFY_SSL = var.splunk_hec_verify_ssl
      MAX_RUNTIME_SECONDS   = tostring(var.metrics_max_runtime_seconds)
    }
  }
}

resource "aws_lambda_function" "logs" {
  function_name    = "${var.name_prefix}-logs"
  role             = aws_iam_role.logs.arn
  runtime          = var.runtime
  handler          = "mariadb_logs_collector.lambda_handler"
  filename         = var.logs_zip
  source_code_hash = filebase64sha256(var.logs_zip)
  timeout          = var.logs_timeout
  memory_size      = var.logs_memory_size

  # Pin to a single concurrent execution: two overlapping runs would race the
  # single S3 checkpoint object (last-writer-wins).
  reserved_concurrent_executions = 1

  environment {
    variables = {
      SECRETS_ARN           = var.logs_secret_arn
      MARIADB_API_URL       = var.mariadb_api_url
      SPLUNK_HEC_URL        = var.splunk_hec_url
      SPLUNK_INDEX          = var.splunk_index_logs
      SPLUNK_HEC_VERIFY_SSL = var.splunk_hec_verify_ssl
      MAX_RUNTIME_SECONDS   = tostring(var.logs_max_runtime_seconds)
      CHECKPOINT_FILE       = "s3://${aws_s3_bucket.checkpoint.id}/${local.checkpoint_key}"
    }
  }
}

# ---------------------------------------------------------------------------
# EventBridge Scheduler: role + schedules
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name_prefix}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_policy" {
  statement {
    sid       = "InvokeFunctions"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.metrics.arn, aws_lambda_function.logs.arn]
  }
  dynamic "statement" {
    for_each = var.enable_dlq ? [1] : []
    content {
      sid       = "SendToDlq"
      actions   = ["sqs:SendMessage"]
      resources = [local.dlq_arn]
    }
  }
}

resource "aws_iam_role_policy" "scheduler_policy" {
  name   = "invoke-and-dlq"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_policy.json
}

resource "aws_scheduler_schedule" "metrics" {
  name                         = "${var.name_prefix}-metrics"
  state                        = var.metrics_schedule_state
  schedule_expression          = var.metrics_schedule
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.metrics.arn
    role_arn = aws_iam_role.scheduler.arn

    dynamic "dead_letter_config" {
      for_each = var.enable_dlq ? [1] : []
      content {
        arn = local.dlq_arn
      }
    }
  }
}

resource "aws_scheduler_schedule" "logs" {
  name                         = "${var.name_prefix}-logs"
  state                        = var.logs_schedule_state
  schedule_expression          = var.logs_schedule
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.logs.arn
    role_arn = aws_iam_role.scheduler.arn

    dynamic "dead_letter_config" {
      for_each = var.enable_dlq ? [1] : []
      content {
        arn = local.dlq_arn
      }
    }
  }
}
