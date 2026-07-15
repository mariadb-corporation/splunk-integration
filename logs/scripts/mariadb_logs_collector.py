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
        self.checkpoint_file = os.environ.get(
            "CHECKPOINT_FILE", "./mariadb_checkpoint.json"
        )

        # Splunk HEC configuration
        self.splunk_hec_url = os.environ.get("SPLUNK_HEC_URL")
        self.splunk_hec_token = os.environ.get("SPLUNK_HEC_TOKEN")
        self.splunk_index = os.environ.get("SPLUNK_INDEX", "mariadb_logs")
        self.splunk_source = os.environ.get("SPLUNK_SOURCE", "mariadb_logs_api")
        self.splunk_sourcetype = os.environ.get("SPLUNK_SOURCETYPE", "mariadb:logs")
        self.batch_size = int(os.environ.get("LOGS_BATCH_SIZE", "100"))
        self.max_retries = int(os.environ.get("LOGS_MAX_RETRIES", "3"))
        self.retry_delay = int(os.environ.get("LOGS_RETRY_DELAY", "5"))
        self.verify_ssl = os.environ.get("SPLUNK_HEC_VERIFY_SSL", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        # API endpoints
        self.logs_query_endpoint = f"{self.api_url}/observability/v2/logs/query"
        self.logs_archive_endpoint = f"{self.api_url}/observability/v2/logs/archive"
        self.logs_servers_endpoint = f"{self.api_url}/observability/v2/logs/servers"

        self._validate_config()

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
    def load_checkpoint(self) -> Dict:
        """Load the checkpoint (last-seen timestamp per log archive)."""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, "r") as f:
                    return json.load(f)
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

            checkpoint_dir = os.path.dirname(self.checkpoint_file)
            if checkpoint_dir:
                os.makedirs(checkpoint_dir, exist_ok=True)

            with open(self.checkpoint_file, "w") as f:
                json.dump(
                    {
                        "startTime": start_time,
                        "endTime": end_time,
                        "logs_stat": logs_stat,
                    },
                    f,
                )
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
    def run(self) -> int:
        """Run a single collection cycle."""
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

                if send_failed:
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


def run_daemon(interval: int = 300) -> int:
    """Run logs collection in daemon mode with continuous polling."""
    global shutdown_requested

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

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
  LOGS_BATCH_SIZE         Events per HEC batch (default: 100)
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
        help="Polling interval in seconds for daemon mode (default: 300)",
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
