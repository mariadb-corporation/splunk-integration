variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for all created resource names."
  type        = string
  default     = "mariadb-splunk"
}

variable "runtime" {
  description = "Lambda Python runtime."
  type        = string
  default     = "python3.12"
}

# ---------------------------------------------------------------------------
# Deployment packages (produced by ../build.sh)
# ---------------------------------------------------------------------------
variable "metrics_zip" {
  description = "Path to the metrics Lambda deployment zip."
  type        = string
  default     = "../dist/metrics_lambda.zip"
}

variable "logs_zip" {
  description = "Path to the logs Lambda deployment zip."
  type        = string
  default     = "../dist/logs_lambda.zip"
}

# ---------------------------------------------------------------------------
# Secrets (create these in Secrets Manager BEFORE applying; pass their ARNs).
# Each secret's value must be JSON, e.g.
#   {"MARIADB_API_KEY": "...", "SPLUNK_HEC_TOKEN": "..."}
# ---------------------------------------------------------------------------
variable "metrics_secret_arn" {
  description = "Secrets Manager ARN for the metrics collector's credentials."
  type        = string
}

variable "logs_secret_arn" {
  description = "Secrets Manager ARN for the logs collector's credentials."
  type        = string
}

# ---------------------------------------------------------------------------
# Splunk / MariaDB configuration (non-secret; passed as Lambda env vars)
# ---------------------------------------------------------------------------
variable "splunk_hec_url" {
  description = "Splunk HEC endpoint URL (without path)."
  type        = string
}

variable "mariadb_api_url" {
  description = "MariaDB Cloud API base URL."
  type        = string
  default     = "https://api.skysql.com"
}

variable "splunk_index_metrics" {
  description = "Target Splunk metrics-type index."
  type        = string
  default     = "mariadb_metrics"
}

variable "splunk_index_logs" {
  description = "Target Splunk events index for logs."
  type        = string
  default     = "mariadb_logs"
}

variable "splunk_hec_verify_ssl" {
  description = "Verify the Splunk HEC TLS certificate (\"true\"/\"false\")."
  type        = string
  default     = "true"
}

# ---------------------------------------------------------------------------
# Schedules. EventBridge Scheduler's finest granularity is 1 minute, so the
# metrics collector's 30s floor is not reachable from a schedule.
# ---------------------------------------------------------------------------
variable "metrics_schedule" {
  description = "Schedule expression for the metrics collector."
  type        = string
  default     = "rate(1 minute)"
}

variable "logs_schedule" {
  description = "Schedule expression for the logs collector."
  type        = string
  default     = "rate(5 minutes)"
}

variable "metrics_schedule_state" {
  description = "Whether the metrics schedule is active. Set to DISABLED to suspend it."
  type        = string
  default     = "ENABLED"
  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.metrics_schedule_state)
    error_message = "metrics_schedule_state must be ENABLED or DISABLED."
  }
}

variable "logs_schedule_state" {
  description = "Whether the logs schedule is active. Set to DISABLED to suspend it."
  type        = string
  default     = "ENABLED"
  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.logs_schedule_state)
    error_message = "logs_schedule_state must be ENABLED or DISABLED."
  }
}

# ---------------------------------------------------------------------------
# Function sizing
# ---------------------------------------------------------------------------
variable "metrics_timeout" {
  description = "Metrics Lambda timeout (seconds)."
  type        = number
  default     = 120
}

variable "logs_timeout" {
  description = "Logs Lambda timeout (seconds). Archive download/parse can be slow."
  type        = number
  default     = 300
}

variable "metrics_max_runtime_seconds" {
  description = <<-EOT
    Soft runtime budget (seconds) for the metrics function. It stops at a safe
    boundary once this elapses, before the Lambda hard timeout, and is also
    auto-capped to the function's actual remaining time.
  EOT
  type        = number
  default     = 270
}

variable "logs_max_runtime_seconds" {
  description = <<-EOT
    Soft runtime budget (seconds) for the logs function. It stops between
    archives (after saving the checkpoint) once this elapses, leaving headroom
    before the Lambda hard timeout; also auto-capped to the actual remaining time.
  EOT
  type        = number
  default     = 180
}

variable "metrics_memory_size" {
  description = "Metrics Lambda memory (MB)."
  type        = number
  default     = 256
}

variable "logs_memory_size" {
  description = "Logs Lambda memory (MB). Archive download/parse is memory-heavier."
  type        = number
  default     = 2048
}

variable "enable_dlq" {
  description = "Create an SQS dead-letter queue for failed scheduled invocations."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Logs checkpoint storage (S3)
# ---------------------------------------------------------------------------
variable "checkpoint_bucket" {
  description = <<-EOT
    Name of the S3 bucket for the logs collector's dedup checkpoint. Leave
    empty to derive it as "<name_prefix>-checkpoints-<account_id>". The stack
    creates this bucket, so the name must not already exist.
  EOT
  type        = string
  default     = ""
}

variable "checkpoint_key" {
  description = "S3 object key for the logs dedup checkpoint."
  type        = string
  default     = "logs/checkpoint.json"
}
