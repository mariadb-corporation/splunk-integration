# Copyright (c) 2026 MariaDB plc. All rights reserved.
#
# This software is intended for use by MariaDB subscription customers only.
# Unauthorized modification, copying or distribution is prohibited.
# MariaDB product terms at https://mariadb.com/terms/ apply.

"""
MariaDB Cloud Metrics Collector for Splunk Cloud Platform
Polls MariaDB Cloud Metrics API and sends metrics to Splunk HEC endpoint
"""

import os
import sys
import json
import time
import logging
import requests
import signal
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mariadb_metrics")


class MetricsCollector:
    """Collects metrics from MariaDB Cloud API and sends to Splunk HEC"""

    def __init__(self):
        self.mariadb_api_key = os.environ.get("MARIADB_API_KEY")
        self.mariadb_api_url = os.environ.get(
            "MARIADB_API_URL", "https://api.skysql.com"
        )
        self.splunk_hec_url = os.environ.get("SPLUNK_HEC_URL")
        self.splunk_hec_token = os.environ.get("SPLUNK_HEC_TOKEN")
        self.splunk_index = os.environ.get("SPLUNK_INDEX", "mariadb_metrics")
        self.splunk_source = os.environ.get("SPLUNK_SOURCE", "mariadbl_metrics_api")
        self.splunk_sourcetype = os.environ.get("SPLUNK_SOURCETYPE", "metrics")
        self.batch_size = self._int_env("METRICS_BATCH_SIZE", "100", minimum=1)
        self.max_retries = self._int_env("METRICS_MAX_RETRIES", "3", minimum=1)
        self.retry_delay = self._int_env("METRICS_RETRY_DELAY", "5", minimum=0)
        self.verify_ssl = os.environ.get("SPLUNK_HEC_VERIFY_SSL", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        self._validate_config()

    @staticmethod
    def _int_env(name: str, default: str, minimum: Optional[int] = None) -> int:
        """Read an integer env var, failing fast with a clear message.

        A non-numeric value (typo, stray character from a k8s ConfigMap, etc.)
        would otherwise raise a cryptic ValueError from int() and, in daemon
        mode, abort the process before the collection loop even starts. Enforce
        an optional lower bound so values like batch_size=0 can't slip through.
        """
        raw = os.environ.get(name, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be an integer (got {raw!r})")
        if minimum is not None and value < minimum:
            raise ValueError(f"{name} must be >= {minimum} (got {value})")
        return value

    def _validate_config(self):
        """Validate required configuration"""
        if not self.mariadb_api_key:
            raise ValueError("MARIADB_API_KEY environment variable is required")
        if not self.splunk_hec_url:
            raise ValueError("SPLUNK_HEC_URL environment variable is required")
        if not self.splunk_hec_token:
            raise ValueError("SPLUNK_HEC_TOKEN environment variable is required")

        logger.info("Configuration validated successfully")
        logger.info(f"MariaDB Cloud API URL: {self.mariadb_api_url}")
        logger.info(f"Splunk HEC URL: {self.splunk_hec_url}")
        logger.info(f"Splunk Index: {self.splunk_index}")

    def fetch_mariadb_metrics(self) -> Optional[str]:
        """Fetch metrics from MariaDB Cloud API in Prometheus format"""
        url = f"{self.mariadb_api_url}/observability/v2/metrics"
        headers = {"X-Api-Key": self.mariadb_api_key, "Accept": "text/plain"}

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Fetching metrics from MariaDB Cloud API (attempt {attempt + 1}/{self.max_retries})"
                )
                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    logger.info(
                        f"Successfully fetched metrics ({len(response.text)} bytes)"
                    )
                    return response.text
                elif response.status_code == 401:
                    logger.error("Authentication failed - check MARIADB_API_KEY")
                    return None
                elif response.status_code == 404:
                    logger.error("Metrics endpoint not found - check API URL")
                    return None
                else:
                    logger.warning(
                        f"API returned status {response.status_code}: {response.text[:200]}"
                    )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Request timeout (attempt {attempt + 1}/{self.max_retries})"
                )
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching metrics: {e}")

            if attempt < self.max_retries - 1:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

        logger.error("Failed to fetch metrics after all retries")
        return None

    def parse_prometheus_format(self, text: str) -> List[Dict]:
        """Parse Prometheus text format into structured metrics"""
        metrics = []
        current_metric_name = None
        current_metric_type = None
        current_metric_help = None

        for line in text.split("\n"):
            line = line.strip()

            if not line or line.startswith("#"):
                if line.startswith("# HELP"):
                    parts = line.split(" ", 3)
                    if len(parts) >= 4:
                        current_metric_name = parts[2]
                        current_metric_help = parts[3]
                elif line.startswith("# TYPE"):
                    parts = line.split(" ", 3)
                    if len(parts) >= 4:
                        current_metric_name = parts[2]
                        current_metric_type = parts[3]
                continue

            try:
                metric_data = self._parse_metric_line(line)
                if metric_data:
                    metric_data["metric_type"] = current_metric_type
                    metric_data["metric_help"] = current_metric_help
                    metrics.append(metric_data)
            except Exception as e:
                logger.debug(f"Failed to parse line: {line[:100]} - {e}")

        logger.info(f"Parsed {len(metrics)} metrics from Prometheus format")
        return metrics

    def _parse_metric_line(self, line: str) -> Optional[Dict]:
        """Parse a single Prometheus metric line"""
        if "{" in line:
            metric_name, rest = line.split("{", 1)
            # Find the '}' that closes the label set, ignoring any '}' inside a
            # quoted label value, then parse the labels honoring escapes.
            labels_str, value_str = self._split_labels(rest)
            labels = self._parse_labels(labels_str)

            value = float(value_str.strip().split()[0])

            return {
                "metric_name": metric_name.strip(),
                "labels": labels,
                "value": value,
            }
        else:
            parts = line.split()
            if len(parts) >= 2:
                return {"metric_name": parts[0], "labels": {}, "value": float(parts[1])}

        return None

    @staticmethod
    def _split_labels(rest: str) -> Tuple[str, str]:
        """Split a metric line's remainder (after '{') into (labels, value).

        Scans for the '}' that closes the label set while skipping any '}' that
        appears inside a quoted label value. Prometheus allows '}' (and escaped
        quotes/backslashes) inside label values, so a naive ``split('}')`` would
        truncate the labels and corrupt the value. Returns the raw label block
        (without braces) and the remainder of the line after the closing '}'.
        """
        in_quote = False
        escaped = False
        for i, ch in enumerate(rest):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_quote = not in_quote
                continue
            if ch == "}" and not in_quote:
                return rest[:i], rest[i + 1 :]
        raise ValueError("unterminated label set (no closing '}')")

    @staticmethod
    def _parse_labels(labels_str: str) -> Dict[str, str]:
        """Parse a Prometheus label block (the text between '{' and '}').

        Splits key=value pairs on commas that are outside quoted values and
        unescapes the Prometheus escape sequences (\\", \\\\, \\n) in each value.
        """
        labels: Dict[str, str] = {}
        i = 0
        n = len(labels_str)
        while i < n:
            # Skip separators / whitespace between pairs.
            while i < n and labels_str[i] in ", \t":
                i += 1
            if i >= n:
                break

            eq = labels_str.find("=", i)
            if eq == -1:
                break
            key = labels_str[i:eq].strip()

            j = eq + 1
            while j < n and labels_str[j] in " \t":
                j += 1

            if j < n and labels_str[j] == '"':
                # Quoted value: consume up to the closing unescaped quote.
                j += 1
                start = j
                escaped = False
                while j < n:
                    ch = labels_str[j]
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        break
                    j += 1
                if key:
                    labels[key] = MetricsCollector._unescape_label_value(
                        labels_str[start:j]
                    )
                i = j + 1  # skip past the closing quote
            else:
                # Unquoted value fallback: take up to the next comma.
                comma = labels_str.find(",", j)
                end = n if comma == -1 else comma
                if key:
                    labels[key] = labels_str[j:end].strip()
                i = end

        return labels

    @staticmethod
    def _unescape_label_value(s: str) -> str:
        """Decode Prometheus label-value escapes: \\" -> ", \\\\ -> \\, \\n -> LF."""
        out = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch == "\\" and i + 1 < n:
                nxt = s[i + 1]
                if nxt == "n":
                    out.append("\n")
                elif nxt == "\\":
                    out.append("\\")
                elif nxt == '"':
                    out.append('"')
                else:
                    # Unknown escape: preserve the backslash and the next char.
                    out.append("\\")
                    out.append(nxt)
                i += 2
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    def transform_to_hec_events(self, metrics: List[Dict]) -> List[Dict]:
        """Transform Prometheus metrics to Splunk HEC event format"""
        events = []
        current_time = time.time()

        for metric in metrics:
            event = {
                "time": current_time,
                "source": self.splunk_source,
                "sourcetype": self.splunk_sourcetype,
                "index": self.splunk_index,
                "event": "metric",
                "fields": {
                    "metric_name": f"mariadb.{metric['metric_name']}",
                    "_value": metric["value"],
                },
            }

            for label_key, label_value in metric.get("labels", {}).items():
                event["fields"][label_key] = label_value

            if metric.get("metric_type"):
                event["fields"]["metric_type"] = metric["metric_type"]

            events.append(event)

        logger.info(f"Transformed {len(events)} metrics to HEC event format")
        return events

    def send_to_splunk_hec(self, events: List[Dict]) -> bool:
        """Send events to Splunk HEC endpoint in batches"""
        if not events:
            logger.warning("No events to send")
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

            payload = "\n".join([json.dumps(event) for event in batch])

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
                        logger.error(
                            "HEC authentication failed - check SPLUNK_HEC_TOKEN"
                        )
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

        logger.info(
            f"Successfully sent {sent_count}/{total_events} events to Splunk HEC"
        )
        return sent_count == total_events

    def run(self) -> int:
        """Main execution flow"""
        try:
            logger.info("Starting MariaDB Cloud metrics collection")

            prometheus_text = self.fetch_mariadb_metrics()
            if not prometheus_text:
                logger.error("Failed to fetch metrics from MariaDB Cloud API")
                return 1

            metrics = self.parse_prometheus_format(prometheus_text)
            if not metrics:
                logger.warning("No metrics parsed from response")
                return 0

            events = self.transform_to_hec_events(metrics)

            success = self.send_to_splunk_hec(events)
            if not success:
                logger.error("Failed to send metrics to Splunk HEC")
                return 1

            logger.info("Metrics collection completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Unexpected error in main execution: {e}", exc_info=True)
            return 1


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def run_daemon(interval=60):
    """Run metrics collection in daemon mode with continuous polling"""
    global shutdown_requested

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Guard against a zero/negative interval, which would skip the sleep loop
    # entirely and busy-loop the API/HEC calls (pinning CPU, risking rate limits).
    if interval < 1:
        logger.warning(
            f"Invalid interval {interval}; using minimum of 1 second"
        )
        interval = 1

    logger.info(f"Starting daemon mode with {interval} second interval")
    logger.info("Press Ctrl+C to stop gracefully")

    collector = MetricsCollector()

    while not shutdown_requested:
        try:
            logger.info("Starting metrics collection cycle")
            exit_code = collector.run()

            if exit_code != 0:
                logger.warning(f"Collection cycle completed with exit code {exit_code}")

            if not shutdown_requested:
                logger.info(f"Sleeping for {interval} seconds until next collection")
                # Sleep in small increments to allow quick shutdown
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
    """Entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(
        description=(
            "MariaDB Cloud Metrics Collector for Splunk. Polls the MariaDB Cloud "
            "Metrics API (Prometheus format) and sends the metrics to a Splunk "
            "HTTP Event Collector (HEC) endpoint. Configuration is read entirely "
            "from environment variables (see below)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  MARIADB_API_KEY         (required) MariaDB Cloud API key
  MARIADB_API_URL         MariaDB Cloud API base URL (default: https://api.skysql.com)
  SPLUNK_HEC_URL          (required) Splunk HEC endpoint URL (without path)
  SPLUNK_HEC_TOKEN        (required) Splunk HEC token
  SPLUNK_HEC_VERIFY_SSL   Verify HEC TLS cert: true/false (default: true)
  SPLUNK_INDEX            Target index (default: mariadb_metrics)
  SPLUNK_SOURCE           Source field (default: mariadbl_metrics_api)
  SPLUNK_SOURCETYPE       Sourcetype field (default: metrics)
  METRICS_BATCH_SIZE      Events per HEC batch (default: 100)
  METRICS_MAX_RETRIES     Max retry attempts (default: 3)
  METRICS_RETRY_DELAY     Retry delay in seconds (default: 5)

Examples:
  # Run once (default)
  %(prog)s

  # Run as daemon with a 60 second interval
  %(prog)s --daemon --interval 60

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
        default=60,
        help="Polling interval in seconds for daemon mode (default: 60)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (e.g. Prometheus line-parse failures)",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        if args.daemon:
            # Run in daemon mode
            exit_code = run_daemon(interval=args.interval)
        else:
            # Run once
            collector = MetricsCollector()
            exit_code = collector.run()

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
