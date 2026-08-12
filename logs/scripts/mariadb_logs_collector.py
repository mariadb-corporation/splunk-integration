# Copyright (c) 2026 MariaDB plc. All rights reserved.
#
# This software is intended for use by MariaDB subscription customers only.
# Unauthorized modification, copying or distribution is prohibited.
# MariaDB product terms at https://mariadb.com/terms/ apply.

"""
MariaDB Cloud Logs API Input Script for Splunk Cloud Platform
Polls the MariaDB Cloud Logs API and sends log lines to a Splunk HTTP Event
Collector (HEC) endpoint.
"""

import os
import sys
import io
import json
import time
import zipfile
import re
import signal
import logging
import argparse
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mariadb_logs")


class MariaDBLogsCollector:
    """Collects logs from the MariaDB Cloud Logs API and sends them to Splunk HEC."""

    def __init__(self):
        # MariaDB Cloud API configuration
        self.api_url = os.environ.get("MARIADB_API_URL", "https://api.skysql.com")
        self.api_key = os.environ.get("MARIADB_API_KEY")
        # CHECKPOINT_FILE may be a local path (standalone) or an
        # ``s3://bucket/key`` URI (Lambda, where the local filesystem is
        # ephemeral). See load_checkpoint/save_checkpoint.
        self.checkpoint_file = os.environ.get(
            "CHECKPOINT_FILE", "./mariadb_checkpoint.json"
        )
        # Lazily created boto3 S3 client, only when an s3:// checkpoint is used.
        self._s3 = None

        # Splunk HEC configuration
        self.splunk_hec_url = os.environ.get("SPLUNK_HEC_URL")
        self.splunk_hec_token = os.environ.get("SPLUNK_HEC_TOKEN")
        self.splunk_index = os.environ.get("SPLUNK_INDEX", "mariadb_logs")
        self.splunk_source = os.environ.get("SPLUNK_SOURCE", "mariadb_logs_api")
        self.splunk_sourcetype = os.environ.get("SPLUNK_SOURCETYPE", "mariadb:logs")
        self.batch_size = int(os.environ.get("LOGS_BATCH_SIZE", "1000"))
        self.max_retries = int(os.environ.get("LOGS_MAX_RETRIES", "3"))
        self.retry_delay = int(os.environ.get("LOGS_RETRY_DELAY", "5"))
        self.verify_ssl = os.environ.get("SPLUNK_HEC_VERIFY_SSL", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        # When TLS verification is disabled the user opted out deliberately, so
        # silence urllib3's per-request "Unverified HTTPS request" warning.
        if not self.verify_ssl:
            try:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

        # API endpoints
        self.logs_query_endpoint = f"{self.api_url}/observability/v2/logs/query"
        self.logs_archive_endpoint = f"{self.api_url}/observability/v2/logs/archive"
        self.logs_servers_endpoint = f"{self.api_url}/observability/v2/logs/servers"

        # Optional monotonic deadline (seconds) after which run() stops between
        # archives. Set per-cycle by run(); None means unbounded (standalone).
        self._deadline = None

        self._validate_config()

    def _deadline_reached(self) -> bool:
        """True once the soft runtime deadline has passed (see run/lambda_handler)."""
        return self._deadline is not None and time.monotonic() >= self._deadline

    def _validate_config(self):
        """Validate required configuration."""
        if not self.api_key:
            raise ValueError("MARIADB_API_KEY environment variable is required")
        if not self.splunk_hec_url:
            raise ValueError("SPLUNK_HEC_URL environment variable is required")
        if not self.splunk_hec_token:
            raise ValueError("SPLUNK_HEC_TOKEN environment variable is required")

        logger.info("Configuration validated successfully")
        logger.info(f"MariaDB Cloud API URL: {self.api_url}")
        logger.info(f"Splunk HEC URL: {self.splunk_hec_url}")
        logger.info(f"Splunk Index: {self.splunk_index}")

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------
    @staticmethod
    def _is_s3(path: str) -> bool:
        """True if the checkpoint location is an s3:// URI."""
        return isinstance(path, str) and path.startswith("s3://")

    @staticmethod
    def _parse_s3_uri(uri: str) -> Tuple[str, str]:
        """Split ``s3://bucket/key`` into ``(bucket, key)``."""
        bucket, _, key = uri[len("s3://"):].partition("/")
        if not bucket or not key:
            raise ValueError(
                f"Invalid S3 checkpoint URI: {uri!r} (expected s3://bucket/key)"
            )
        return bucket, key

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        """True if an S3 error means the checkpoint object does not exist yet."""
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        return code in ("NoSuchKey", "404") or exc.__class__.__name__ == "NoSuchKey"

    def _s3_client(self):
        """Return a cached boto3 S3 client (imported lazily)."""
        if self._s3 is None:
            import boto3  # lazy: only required for s3:// checkpoints (Lambda)

            self._s3 = boto3.client("s3")
        return self._s3

    def _read_checkpoint(self) -> Optional[str]:
        """Read the raw checkpoint JSON, or None if it does not exist yet."""
        if self._is_s3(self.checkpoint_file):
            bucket, key = self._parse_s3_uri(self.checkpoint_file)
            try:
                resp = self._s3_client().get_object(Bucket=bucket, Key=key)
            except Exception as e:
                if self._is_not_found(e):
                    return None
                raise
            return resp["Body"].read().decode("utf-8")

        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, "r") as f:
                return f.read()
        return None

    def _write_checkpoint(self, payload: str):
        """Persist the raw checkpoint JSON to S3 or the local file."""
        if self._is_s3(self.checkpoint_file):
            bucket, key = self._parse_s3_uri(self.checkpoint_file)
            self._s3_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
            return

        checkpoint_dir = os.path.dirname(self.checkpoint_file)
        if checkpoint_dir:
            os.makedirs(checkpoint_dir, exist_ok=True)
        with open(self.checkpoint_file, "w") as f:
            f.write(payload)

    def load_checkpoint(self) -> Dict:
        """Load the checkpoint (last-seen timestamp per log archive)."""
        try:
            raw = self._read_checkpoint()
            if raw is not None:
                return json.loads(raw)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")

        # Only logs_stat (per-archive dedup state) is consumed on load; the
        # query window is recomputed each cycle in run().
        return {"logs_stat": {}}

    def save_checkpoint(self, start_time: str, end_time: str, logs_stat: Dict):
        """Persist the checkpoint, pruning log_ids older than 2 days."""
        try:
            # Drop any log_ids whose last_timestamp is more than 2 days older
            # than start_time to keep the checkpoint small.
            try:
                start_str = (start_time or "").rstrip("Z")
                if start_str:
                    cutoff = datetime.fromisoformat(start_str) - timedelta(days=2)
                    for lid in list(logs_stat.keys()):
                        ts_str = (logs_stat.get(lid) or {}).get("last_timestamp")
                        if not ts_str:
                            continue
                        try:
                            ts_dt = datetime.fromisoformat(str(ts_str).rstrip("Z"))
                        except ValueError:
                            continue
                        if ts_dt < cutoff:
                            del logs_stat[lid]
            except Exception as prune_err:
                logger.warning(
                    f"Failed to prune stale log_stat entries: {prune_err}"
                )

            payload = json.dumps(
                {
                    "startTime": start_time,
                    "endTime": end_time,
                    "logs_stat": logs_stat,
                }
            )
            self._write_checkpoint(payload)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    @staticmethod
    def update_log_stat(logs_stat: Dict, log_id: str, last_timestamp):
        """Update the per-log_id last_timestamp."""
        if log_id not in logs_stat:
            logs_stat[log_id] = {"last_timestamp": last_timestamp}
        else:
            logs_stat[log_id]["last_timestamp"] = last_timestamp

    # ------------------------------------------------------------------
    # MariaDB Cloud Logs API
    # ------------------------------------------------------------------
    def fetch_servers(self) -> List[str]:
        """Fetch the list of server data source IDs to use as serverContext."""
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        try:
            response = requests.get(
                self.logs_servers_endpoint, headers=headers, timeout=30
            )
            response.raise_for_status()
            servers = response.json()
            return [
                server["serverDataSourceId"]
                for server in servers.get("servers", [])
            ]
        except Exception as e:
            logger.error(f"Failed to fetch servers: {e}")
            return []

    def fetch_log_metadata(
        self,
        from_date: str,
        to_date: str,
        server_context: List[str],
        limit: int = 1000,
        offset: int = 0,
    ) -> Optional[Dict]:
        """Fetch log-archive metadata from the MariaDB Cloud Logs API.

        server_context is fetched once per cycle by the caller and passed in,
        rather than re-fetched on every pagination page.
        """
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        payload = {
            "fromDate": from_date,
            "toDate": to_date,
            "limit": limit,
            "offset": offset,
            "logTypes": ["error-log", "audit-log", "maxscale-log"],
            "orderByField": "startTime",
            "orderByDirection": "asc",
            "serverContext": server_context,
        }

        try:
            response = requests.post(
                self.logs_query_endpoint, headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None

    def fetch_log_archive(self, log_id: str, log_format: str = "json") -> Optional[bytes]:
        """Download a log archive (zip) for the given log ID."""
        headers = {"X-API-KEY": self.api_key}
        params = {"logIds": log_id, "logFormat": log_format}
        try:
            response = requests.get(
                self.logs_archive_endpoint,
                headers=headers,
                params=params,
                timeout=60,
                stream=True,
            )
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch archive for log ID {log_id}: {e}")
            return None

    def parse_log_archive(
        self, archive_content: bytes, log_type: str = "error-log", last_timestamp=None
    ) -> Tuple[List[Dict], Optional[str]]:
        """Parse a log archive (zip) and extract individual log lines.

        `last_timestamp` is the dedup seed from the checkpoint: lines strictly
        older than it are skipped. It is treated as immutable here — the return
        value is the **maximum** timestamp seen (not the last line processed),
        so archives whose lines are not strictly ascending do not cause later
        out-of-order lines to be dropped on the next cycle.
        """
        log_lines: List[Dict] = []
        file_name = None
        skipped_logs = 0
        max_timestamp = last_timestamp  # running max returned to the caller
        prev_line_ts = None  # last parsed timestamp, inherited by continuation lines
        try:
            with zipfile.ZipFile(io.BytesIO(archive_content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.is_dir():
                        continue
                    try:
                        with zip_file.open(file_info) as file_obj:
                            content = file_obj.read()
                            try:
                                file_name = file_info.filename
                                text_content = content.decode("utf-8")
                                for line in text_content.splitlines():
                                    message = line.strip()
                                    if not message:
                                        continue
                                    # Reset per line so a line without its own
                                    # level marker does not inherit the prior
                                    # line's level.
                                    log_level = "INFO"
                                    parsed_ts = None
                                    try:
                                        msg = json.loads(message)
                                        # Records are JSON objects with a "log"
                                        # field; guard against non-dict JSON.
                                        if isinstance(msg, dict):
                                            message = msg.get("log", msg)
                                        else:
                                            message = msg

                                        if isinstance(message, str):
                                            if log_type == "audit-log":
                                                parts = message.split(",", 1)
                                                if parts:
                                                    ts_str = parts[0]
                                                    try:
                                                        dt = datetime.strptime(
                                                            ts_str, "%Y%m%d %H:%M:%S"
                                                        )
                                                        parsed_ts = dt.isoformat() + "Z"
                                                        log_level = "INFO"
                                                    except ValueError:
                                                        pass
                                            elif log_type in ("error-log", "maxscale-log"):
                                                m_ts = re.match(
                                                    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)",
                                                    message,
                                                )
                                                if m_ts:
                                                    parsed_ts = m_ts.group(1)
                                            if log_type == "error-log":
                                                m_level = re.search(r"\[(\w+)\]", message)
                                                if m_level:
                                                    log_level = m_level.group(1)
                                            elif log_type == "maxscale-log":
                                                m_level = re.search(
                                                    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+(\w+)\s*:",
                                                    message,
                                                )
                                                if m_level:
                                                    log_level = m_level.group(1)
                                    except ValueError:
                                        logger.warning(
                                            f"Could not parse message as JSON: {message}"
                                        )
                                        log_level = None

                                    if parsed_ts:
                                        prev_line_ts = parsed_ts
                                        timestamp = parsed_ts
                                    else:
                                        # Continuation / unparseable line: inherit
                                        # the previous line's timestamp (or the
                                        # dedup seed) so it stays deduplicated
                                        # instead of getting a fresh utcnow() that
                                        # would re-send it on every cycle.
                                        timestamp = (
                                            prev_line_ts
                                            or last_timestamp
                                            or datetime.utcnow().isoformat() + "Z"
                                        )

                                    # Dedup against the immutable seed.
                                    if last_timestamp and timestamp < last_timestamp:
                                        skipped_logs += 1
                                        continue

                                    if max_timestamp is None or timestamp > max_timestamp:
                                        max_timestamp = timestamp

                                    log_lines.append(
                                        {
                                            "filename": file_name,
                                            "message": message,
                                            "timestamp": timestamp,
                                            "log.level": log_level,
                                        }
                                    )
                            except UnicodeDecodeError:
                                logger.warning(
                                    f"Could not decode file {file_info.filename} as UTF-8"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Failed to read file {file_info.filename}: {e}"
                        )
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid zip file: {e}")
        except Exception as e:
            logger.error(f"Failed to parse archive: {e}")

        if skipped_logs:
            logger.debug(f"{file_name}: skipped {skipped_logs} already-seen lines")
        return log_lines, max_timestamp

    # ------------------------------------------------------------------
    # HEC transform + send
    # ------------------------------------------------------------------
    @staticmethod
    def _iso_to_epoch(ts: Optional[str]) -> float:
        """Convert an ISO-8601 timestamp to epoch seconds for the HEC time field.

        Falls back to the current time on any parse failure. Handles a trailing
        'Z' and fractional seconds with more than microsecond precision (e.g.
        nanoseconds emitted by MaxScale).
        """
        if not ts:
            return time.time()
        try:
            s = str(ts).strip()
            if s.endswith("Z"):
                s = s[:-1]
            if "." in s:
                head, frac = s.split(".", 1)
                frac = frac[:6]  # datetime supports at most microseconds
                dt = datetime.strptime(f"{head}.{frac}", "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return time.time()

    def transform_to_hec_events(
        self, log_lines: List[Dict], log_meta: Dict, log_type: str
    ) -> List[Dict]:
        """Transform parsed log lines to Splunk HEC event format."""
        events = []
        for line in log_lines:
            events.append(
                {
                    "time": self._iso_to_epoch(line.get("timestamp")),
                    "source": self.splunk_source,
                    "sourcetype": self.splunk_sourcetype,
                    "index": self.splunk_index,
                    "event": {
                        "message": line.get("message"),
                        "filename": line.get("filename"),
                        "logType": log_type,
                        "log.level": line.get("log.level"),
                        "server": log_meta.get("server"),
                        "service": log_meta.get("service"),
                        "serverDataSourceId": log_meta.get("serverDataSourceId"),
                    },
                }
            )
        return events

    def send_to_splunk_hec(self, events: List[Dict]) -> bool:
        """Send events to the Splunk HEC endpoint in batches."""
        if not events:
            logger.info("No events to send")
            return True

        hec_endpoint = f"{self.splunk_hec_url}/services/collector"
        headers = {
            "Authorization": f"Splunk {self.splunk_hec_token}",
            "Content-Type": "application/json",
        }

        total_events = len(events)
        sent_count = 0

        for i in range(0, total_events, self.batch_size):
            batch = events[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_events + self.batch_size - 1) // self.batch_size

            logger.info(
                f"Sending batch {batch_num}/{total_batches} ({len(batch)} events)"
            )

            payload = "\n".join(json.dumps(event) for event in batch)

            for attempt in range(self.max_retries):
                try:
                    response = requests.post(
                        hec_endpoint,
                        headers=headers,
                        data=payload,
                        timeout=30,
                        verify=self.verify_ssl,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("code") == 0:
                            sent_count += len(batch)
                            logger.info(f"Batch {batch_num} sent successfully")
                            break
                        else:
                            logger.error(f"HEC returned error: {result}")
                    elif response.status_code == 401:
                        logger.error("HEC authentication failed - check SPLUNK_HEC_TOKEN")
                        return False
                    elif response.status_code == 403:
                        logger.error("HEC token disabled or invalid")
                        return False
                    else:
                        logger.warning(
                            f"HEC returned status {response.status_code}: {response.text[:200]}"
                        )

                except requests.exceptions.Timeout:
                    logger.warning(
                        f"HEC request timeout (attempt {attempt + 1}/{self.max_retries})"
                    )
                except requests.exceptions.ConnectionError as e:
                    logger.warning(f"HEC connection error: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error sending to HEC: {e}")

                if attempt < self.max_retries - 1:
                    logger.info(
                        f"Retrying batch {batch_num} in {self.retry_delay} seconds..."
                    )
                    time.sleep(self.retry_delay)
            else:
                logger.error(f"Failed to send batch {batch_num} after all retries")
                return False

        logger.info(f"Successfully sent {sent_count}/{total_events} events to Splunk HEC")
        return sent_count == total_events

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def run(self, deadline: Optional[float] = None) -> int:
        """Run a single collection cycle.

        deadline: optional time.monotonic() value after which the cycle stops
        between archives (used under Lambda to exit before the hard timeout).
        The per-archive checkpoint is always saved before stopping, so the next
        invocation resumes exactly where this one left off. None means run to
        completion (standalone / daemon).
        """
        self._deadline = deadline
        try:
            logger.info("Starting MariaDB Cloud logs collection")

            checkpoint = self.load_checkpoint()
            logs_stat = checkpoint.get("logs_stat", {})

            # Each cycle queries from 00:00 UTC today; per-archive dedup relies
            # on logs_stat[log_id].last_timestamp rather than a sliding window.
            from_date = (
                datetime.utcnow()
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
                + "Z"
            )
            to_date = datetime.utcnow().isoformat() + "Z"

            # Fetch the server context once per cycle (not per pagination page).
            server_context = self.fetch_servers()

            offset = 0
            limit = 100
            total_logs = 0
            total_sent = 0
            send_failed = False
            deadline_stop = False

            while True:
                result = self.fetch_log_metadata(
                    from_date, to_date, server_context, limit, offset
                )
                if not result:
                    break

                logs = result.get("logs", [])
                count = result.get("count", 0)
                if not logs:
                    logger.info(
                        f"No logs found for time range {from_date} to {to_date}"
                    )
                    break

                for log in logs:
                    # Stop between archives if approaching the Lambda timeout.
                    # Every already-sent archive has its checkpoint saved, so the
                    # next invocation resumes cleanly from here.
                    if self._deadline_reached():
                        logger.warning(
                            "Approaching runtime deadline; stopping cycle "
                            "gracefully (checkpoint saved for sent archives)"
                        )
                        deadline_stop = True
                        break

                    if log.get("logType") == "slow-query-log":
                        # TODO: handle slow-query-log separately
                        continue

                    log_id = log.get("id")
                    archive_content = self.fetch_log_archive(log_id)
                    if not archive_content:
                        logger.warning(f"Failed to fetch archive for log ID: {log_id}")
                        continue

                    log_type = log.get("logType")
                    log_lines, last_timestamp = self.parse_log_archive(
                        archive_content,
                        log_type=log_type,
                        last_timestamp=logs_stat.get(log_id, {}).get("last_timestamp"),
                    )

                    if not log_lines:
                        # Nothing new in this archive; leave its checkpoint entry
                        # untouched (avoids storing a sentinel that disables dedup).
                        continue

                    logger.info(
                        f"Extracted {len(log_lines)} log lines from archive {log_id} "
                        f"(name={log.get('name')})"
                    )

                    # Send and checkpoint per archive: bounds memory to one
                    # archive at a time, and persists progress incrementally so a
                    # later failure never re-sends an already-delivered archive.
                    events = self.transform_to_hec_events(log_lines, log, log_type)
                    if not self.send_to_splunk_hec(events):
                        logger.error(
                            f"Failed to send archive {log_id} to Splunk HEC; "
                            f"stopping cycle (checkpoint preserved for sent archives)"
                        )
                        send_failed = True
                        break

                    self.update_log_stat(logs_stat, log_id, last_timestamp)
                    self.save_checkpoint(from_date, to_date, logs_stat)
                    total_sent += len(events)

                if send_failed or deadline_stop:
                    break

                total_logs += len(logs)
                offset += limit
                if total_logs >= count or len(logs) < limit:
                    break

            logger.info(
                f"Sent {total_sent} log lines from {total_logs} archives"
            )

            if send_failed:
                return 1

            if deadline_stop:
                # Not a failure: a clean, checkpointed early exit. The next
                # scheduled invocation continues from the saved checkpoint.
                logger.info(
                    "Logs collection stopped early at runtime deadline; "
                    "remaining archives will be picked up next cycle"
                )
                return 0

            logger.info("Logs collection completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Unexpected error in collection cycle: {e}", exc_info=True)
            return 1


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


# Minimum daemon polling interval (seconds). The logs API is not a
# high-frequency source, so 5 minutes is the floor.
MIN_INTERVAL = 300


def run_daemon(interval: int = 300) -> int:
    """Run logs collection in daemon mode with continuous polling."""
    global shutdown_requested

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Enforce a minimum polling interval. The logs API is not a high-frequency
    # source; polling more often than every 5 minutes adds load without
    # surfacing new log data.
    if interval < MIN_INTERVAL:
        logger.warning(
            f"Invalid interval {interval}; using minimum of {MIN_INTERVAL} seconds"
        )
        interval = MIN_INTERVAL

    logger.info(f"Starting daemon mode with {interval} second interval")
    logger.info("Press Ctrl+C to stop gracefully")

    collector = MariaDBLogsCollector()

    while not shutdown_requested:
        try:
            logger.info("Starting logs collection cycle")
            exit_code = collector.run()
            if exit_code != 0:
                logger.warning(f"Collection cycle completed with exit code {exit_code}")

            if not shutdown_requested:
                logger.info(f"Sleeping for {interval} seconds until next collection")
                for _ in range(interval):
                    if shutdown_requested:
                        break
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}", exc_info=True)
            if not shutdown_requested:
                logger.info(f"Waiting {interval} seconds before retry")
                time.sleep(interval)

    logger.info("Daemon shutdown complete")
    return 0


# ----------------------------------------------------------------------
# AWS Lambda support
# ----------------------------------------------------------------------
# Default soft runtime budget (seconds). The collector stops between archives
# once this elapses, leaving headroom before Lambda's hard timeout, and always
# after saving the checkpoint. Override with MAX_RUNTIME_SECONDS. Also capped by
# the Lambda context's actual remaining time (minus LAMBDA_SAFETY_BUFFER_SECONDS).
MAX_RUNTIME_SECONDS_DEFAULT = "180"
LAMBDA_SAFETY_BUFFER_SECONDS = 30

# Set once boto3 has resolved the Secrets Manager secret, so warm invocations
# of the same container do not re-fetch it.
_secrets_loaded = False


def _compute_deadline(context):
    """Return a time.monotonic() deadline for this invocation.

    Uses MAX_RUNTIME_SECONDS (default 270s), but never runs closer than
    LAMBDA_SAFETY_BUFFER_SECONDS to the Lambda context's actual remaining time,
    so it adapts to whatever timeout the function is configured with.
    """
    max_runtime = int(os.environ.get("MAX_RUNTIME_SECONDS", MAX_RUNTIME_SECONDS_DEFAULT))
    if context is not None and hasattr(context, "get_remaining_time_in_millis"):
        remaining = context.get_remaining_time_in_millis() / 1000.0
        max_runtime = min(max_runtime, remaining - LAMBDA_SAFETY_BUFFER_SECONDS)
    return time.monotonic() + max(1, max_runtime)


def _load_secrets_from_manager():
    """Populate secret env vars from AWS Secrets Manager (Lambda only).

    Controlled by the ``SECRETS_ARN`` env var: the ARN or name of a Secrets
    Manager secret whose ``SecretString`` is a JSON object with keys such as
    ``MARIADB_API_KEY`` / ``SPLUNK_HEC_TOKEN``. Fetched once per container
    (cold start) and cached. Values already present in the environment are
    NOT overwritten, so an explicit env var still wins.

    boto3 is imported lazily so standalone/non-AWS environments (and the unit
    tests) never need it installed. A no-op when ``SECRETS_ARN`` is unset.
    """
    global _secrets_loaded
    secret_ref = os.environ.get("SECRETS_ARN")
    if _secrets_loaded or not secret_ref:
        return

    try:
        import boto3  # lazy: only required under Lambda
    except ImportError:
        logger.warning("SECRETS_ARN set but boto3 is unavailable; skipping secret load")
        return

    resp = boto3.client("secretsmanager").get_secret_value(SecretId=secret_ref)
    raw = resp.get("SecretString")
    if not raw:
        logger.warning(f"Secret {secret_ref} has no SecretString; skipping")
        _secrets_loaded = True
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Secret {secret_ref} is not valid JSON")

    for key, value in data.items():
        # Do not clobber values explicitly provided via the environment.
        os.environ.setdefault(key, str(value))
    _secrets_loaded = True
    logger.info(f"Loaded {len(data)} value(s) from Secrets Manager")


def lambda_handler(event, context):
    """AWS Lambda entry point.

    Runs a single collection cycle — no daemon loop, since the schedule is
    provided by EventBridge. Raises on failure so Lambda records the
    invocation as errored (enabling automatic retries / a DLQ). Returns a
    small status summary only; log data is never returned here.

    The dedup checkpoint must live in a durable store across invocations —
    set CHECKPOINT_FILE to an ``s3://bucket/key`` URI (see load_checkpoint).
    """
    _load_secrets_from_manager()
    exit_code = MariaDBLogsCollector().run(deadline=_compute_deadline(context))
    if exit_code != 0:
        raise RuntimeError(f"Logs collection failed with exit code {exit_code}")
    return {"status": "ok"}


def main():
    """Entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description=(
            "MariaDB Cloud Logs Collector for Splunk. Polls the MariaDB Cloud Logs API, parses "
            "log archives, and sends the lines to a Splunk HTTP Event Collector "
            "(HEC) endpoint. Configuration is read entirely from environment "
            "variables (see below)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  MARIADB_API_KEY          (required) MariaDB Cloud API key
  MARIADB_API_URL          MariaDB Cloud API base URL (default: https://api.skysql.com)
  CHECKPOINT_FILE         Dedup checkpoint path (default: ./mariadb_checkpoint.json)
  SPLUNK_HEC_URL          (required) Splunk HEC endpoint URL (without path)
  SPLUNK_HEC_TOKEN        (required) Splunk HEC token
  SPLUNK_HEC_VERIFY_SSL   Verify HEC TLS cert: true/false (default: true)
  SPLUNK_INDEX            Target index (default: mariadb_logs)
  SPLUNK_SOURCE           Source field (default: mariadb_logs_api)
  SPLUNK_SOURCETYPE       Sourcetype field (default: mariadb:logs)
  LOGS_BATCH_SIZE         Events per HEC batch (default: 1000)
  LOGS_MAX_RETRIES        Max retry attempts (default: 3)
  LOGS_RETRY_DELAY        Retry delay in seconds (default: 5)

Examples:
  # Run once (default)
  %(prog)s

  # Run as daemon with a 5 minute interval
  %(prog)s --daemon --interval 300

  # Run once with DEBUG logging
  %(prog)s --verbose
""",
    )
    parser.add_argument(
        "--daemon", action="store_true", help="Run in daemon mode (continuous polling)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds for daemon mode (default: 300, minimum: 300)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (e.g. per-archive dedup skip counts)",
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        if args.daemon:
            exit_code = run_daemon(interval=args.interval)
        else:
            collector = MariaDBLogsCollector()
            exit_code = collector.run()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
