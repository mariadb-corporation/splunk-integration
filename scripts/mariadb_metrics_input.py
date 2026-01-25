#!/usr/bin/env python3
"""
MariaDB Cloud Metrics Input Script for Splunk Cloud Platform
Polls MariaDB Cloud Metrics API and sends metrics to Splunk HEC endpoint
"""

import os
import sys
import json
import time
import logging
import requests
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
        self.splunk_index = os.environ.get("SPLUNK_INDEX", "main")
        self.splunk_source = os.environ.get("SPLUNK_SOURCE", "mariadbl_metrics_api")
        self.splunk_sourcetype = os.environ.get("SPLUNK_SOURCETYPE", "metrics")
        self.checkpoint_file = os.environ.get(
            "METRICS_CHECKPOINT_FILE", "/tmp/metrics_checkpoint.json"
        )
        self.batch_size = int(os.environ.get("METRICS_BATCH_SIZE", "100"))
        self.max_retries = int(os.environ.get("METRICS_MAX_RETRIES", "3"))
        self.retry_delay = int(os.environ.get("METRICS_RETRY_DELAY", "5"))
        self.verify_ssl = os.environ.get("SPLUNK_HEC_VERIFY_SSL", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        self._validate_config()

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
        logger.info(f"Checkpoint file: {self.checkpoint_file}")

    def load_checkpoint(self) -> Optional[float]:
        """Load the last successful poll timestamp from checkpoint file"""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
                    timestamp = data.get("last_poll_time")
                    if timestamp:
                        logger.info(
                            f"Loaded checkpoint: {datetime.fromtimestamp(timestamp)}"
                        )
                        return timestamp
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")

        return None

    def save_checkpoint(self, timestamp: float):
        """Save the successful poll timestamp to checkpoint file"""
        try:
            checkpoint_dir = os.path.dirname(self.checkpoint_file)
            if checkpoint_dir and not os.path.exists(checkpoint_dir):
                os.makedirs(checkpoint_dir, mode=0o755)

            with open(self.checkpoint_file, "w") as f:
                json.dump(
                    {
                        "last_poll_time": timestamp,
                        "last_poll_datetime": datetime.fromtimestamp(
                            timestamp
                        ).isoformat(),
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Saved checkpoint: {datetime.fromtimestamp(timestamp)}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

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
            labels_str, value_str = rest.split("}", 1)

            labels = {}
            for label_pair in labels_str.split(","):
                if "=" in label_pair:
                    key, val = label_pair.split("=", 1)
                    labels[key.strip()] = val.strip().strip('"')

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

            last_poll_time = self.load_checkpoint()
            current_time = time.time()

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

            self.save_checkpoint(current_time)

            logger.info("Metrics collection completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Unexpected error in main execution: {e}", exc_info=True)
            return 1


def main():
    """Entry point"""
    try:
        collector = MetricsCollector()
        exit_code = collector.run()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
