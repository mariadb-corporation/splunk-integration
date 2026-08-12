# Running the collectors on AWS Lambda

Both MariaDB Cloud → Splunk collectors can run as scheduled AWS Lambda
functions in addition to standalone / daemon mode. Nothing about the standalone
usage changes — the same script gains a `lambda_handler` entry point.

```
EventBridge Scheduler ──▶ metrics Lambda ─────────────────────────▶ Splunk HEC   (stateless)
                            └─▶ Secrets Manager (cold start)

EventBridge Scheduler ──▶ logs Lambda ──▶ S3 (checkpoint get/put) ─▶ Splunk HEC   (stateful,
                            └─▶ Secrets Manager (cold start)                       concurrency = 1)
```

Key design points:

- **Metrics is stateless** — each invocation polls current values and sends them.
- **Logs is stateful** — it keeps a per-archive dedup checkpoint. Lambda's
  filesystem is ephemeral, so the checkpoint is stored in **S3**. Set
  `CHECKPOINT_FILE` to an `s3://bucket/key` URI and the collector transparently
  reads/writes S3 instead of a local file.
- **Secrets** (`MARIADB_API_KEY`, `SPLUNK_HEC_TOKEN`) are pulled from **AWS
  Secrets Manager** at cold start via `SECRETS_ARN`. An explicit environment
  variable of the same name always wins, so you can still inject creds directly
  for testing.
- **`boto3` is not bundled** — it is already in the Lambda runtime. Only
  `requests` is vendored into the deployment package.

---

## 1. Create the secrets

Each function reads a single Secrets Manager secret whose value is a JSON object.
You can use one secret for both or one per function.

```bash
aws secretsmanager create-secret \
  --name mariadb-splunk/metrics \
  --secret-string '{"MARIADB_API_KEY":"<key>","SPLUNK_HEC_TOKEN":"<token>"}'

aws secretsmanager create-secret \
  --name mariadb-splunk/logs \
  --secret-string '{"MARIADB_API_KEY":"<key>","SPLUNK_HEC_TOKEN":"<token>"}'
```

Note the returned ARNs — you pass them to the stack below.

## 2. Build the deployment packages

```bash
deploy/lambda/build.sh
# -> deploy/lambda/dist/metrics_lambda.zip
# -> deploy/lambda/dist/logs_lambda.zip
```

Handlers:

| Function | Handler |
|----------|---------|
| metrics  | `mariadb_metrics_collector.lambda_handler` |
| logs     | `mariadb_logs_collector.lambda_handler` |

## 3. Deploy

Two equivalent stacks are provided — pick one.

### Option A — Terraform (`deploy/lambda/terraform/`)

```bash
cd deploy/lambda/terraform
cp terraform.tfvars.example terraform.tfvars   # then edit the required values
terraform init
terraform apply
```

`terraform.tfvars.example` documents every variable; only `metrics_secret_arn`,
`logs_secret_arn`, and `splunk_hec_url` are required. (Your real
`terraform.tfvars` is gitignored.) You can also pass values ad hoc with
`-var '...'` instead of a tfvars file.

The Terraform stack references the zips directly (`../dist/*.zip`), creates the
S3 checkpoint bucket, IAM roles, both functions, the EventBridge schedules, and
(by default) an SQS dead-letter queue.

### Option B — CloudFormation (`deploy/lambda/cloudformation/`)

Raw CloudFormation cannot upload local zips, so upload them to an S3 artifacts
bucket first, then deploy the stack referencing them:

```bash
aws s3 cp deploy/lambda/dist/metrics_lambda.zip s3://<artifacts-bucket>/metrics_lambda.zip
aws s3 cp deploy/lambda/dist/logs_lambda.zip    s3://<artifacts-bucket>/logs_lambda.zip

aws cloudformation deploy \
  --stack-name mariadb-splunk-lambda \
  --template-file deploy/lambda/cloudformation/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      CodeBucket=<artifacts-bucket> \
      MetricsSecretArn=arn:aws:secretsmanager:...:mariadb-splunk/metrics-XXXX \
      LogsSecretArn=arn:aws:secretsmanager:...:mariadb-splunk/logs-XXXX \
      SplunkHecUrl=https://<instance>.splunkcloud.com:8088
```

`cloudformation/parameters.example.json` lists all parameters with example
values. Copy it to `parameters.json` (gitignored), edit, and use it with the
`create-stack` / `update-stack` APIs instead of `--parameter-overrides`:

```bash
aws cloudformation create-stack \
  --stack-name mariadb-splunk-lambda \
  --template-body file://deploy/lambda/cloudformation/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters file://deploy/lambda/cloudformation/parameters.json
```

---

## Environment variables (set by the stacks)

| Variable | metrics | logs | Notes |
|----------|:------:|:----:|-------|
| `SECRETS_ARN` | ✅ | ✅ | Secrets Manager secret (JSON) fetched at cold start |
| `MARIADB_API_URL` | ✅ | ✅ | Default `https://api.skysql.com` |
| `SPLUNK_HEC_URL` | ✅ | ✅ | HEC endpoint (no path) |
| `SPLUNK_INDEX` | ✅ | ✅ | `mariadb_metrics` / `mariadb_logs` |
| `CHECKPOINT_FILE` | — | ✅ | `s3://<bucket>/logs/checkpoint.json` |

`SPLUNK_HEC_TOKEN` and `MARIADB_API_KEY` come from the secret, not env vars.

## Scheduling

EventBridge Scheduler's finest granularity is **1 minute**, so:

- **metrics** defaults to `rate(1 minute)`. The collector's 30s standalone floor
  is not reachable from a schedule — 1 minute is the practical cadence.
- **logs** defaults to `rate(5 minutes)`, matching the collector's 300s floor.

## Concurrency & the S3 checkpoint

The logs function is pinned to `reserved_concurrent_executions = 1`. The
checkpoint is a single S3 object with last-writer-wins semantics, so two
overlapping runs could clobber each other's dedup state. On the very first run
the object does not exist yet — the collector treats a missing object as an
empty checkpoint (same as a missing local file). The checkpoint is written
**only after a successful HEC send**, per the project's checkpoint contract.

## Suspending a schedule

To pause a collector without tearing anything down, disable its EventBridge
schedule (the functions, IAM, bucket, and secrets stay in place):

- **Terraform:** set `logs_schedule_state = "DISABLED"` (or
  `metrics_schedule_state`) and `terraform apply`.
- **CloudFormation:** set `LogsScheduleState=DISABLED` (or
  `MetricsScheduleState`) and redeploy.

Both default to `ENABLED`. Managing state through the stack avoids drift — a
manual disable in the console would otherwise be reverted on the next apply.
Re-enable by flipping the value back.

## Graceful stop before the hard timeout

Each function enforces a **soft runtime deadline** (`MAX_RUNTIME_SECONDS`) and
stops at a safe boundary before Lambda's hard timeout kills it. Defaults:
**metrics 270s, logs 180s**. The budget is also auto-capped to the function's
actual remaining time (minus a 30s buffer) via the Lambda context, so a function
configured with a shorter timeout stops proportionally sooner.

- **Logs:** stops *between archives*, always after the per-archive checkpoint
  has been saved, then returns cleanly (exit 0). The next scheduled invocation
  resumes from the S3 checkpoint, so no logs are lost or duplicated beyond the
  normal at-least-once boundary. A deadline stop is **not** treated as a
  failure.
- **Metrics:** stops at a batch boundary and returns cleanly; metrics are
  re-polled fresh on the next cycle, so a truncated send just defers the tail.

Adjust the per-function budget if you change a timeout and want different
headroom: Terraform `metrics_max_runtime_seconds` / `logs_max_runtime_seconds`,
CloudFormation `MetricsMaxRuntimeSeconds` / `LogsMaxRuntimeSeconds`.

## Failure handling

`lambda_handler` raises on a non-zero collection result, so a failed cycle is
recorded as a Lambda error. When the DLQ is enabled, failed scheduled
invocations are delivered to the `*-dlq` SQS queue for inspection.

## Updating the code

```bash
deploy/lambda/build.sh
# Terraform: terraform apply   (source_code_hash change triggers an update)
# CloudFormation: re-upload the zips to S3, then aws cloudformation deploy again
```

## Local test of a single invocation

```bash
aws lambda invoke --function-name mariadb-splunk-metrics /dev/stdout
aws lambda invoke --function-name mariadb-splunk-logs    /dev/stdout
```

Logs (human-readable) appear in CloudWatch Logs under
`/aws/lambda/mariadb-splunk-metrics` and `/aws/lambda/mariadb-splunk-logs`.
