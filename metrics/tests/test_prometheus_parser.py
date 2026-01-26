#!/usr/bin/env python3
"""
Unit tests for Prometheus format parser in MariaDB metrics collector
"""

import unittest
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from mariadb_metrics_input import MetricsCollector


class TestPrometheusParser(unittest.TestCase):
    """Test Prometheus format parsing"""

    def setUp(self):
        """Set up test environment"""
        # Set required environment variables
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"

        self.collector = MetricsCollector()

    def test_simple_metric_without_labels(self):
        """Test parsing simple metric without labels"""
        text = "mysql_global_status_threads_connected 42"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(
            metrics[0]["metric_name"], "mysql_global_status_threads_connected"
        )
        self.assertEqual(metrics[0]["value"], 42.0)
        self.assertEqual(metrics[0]["labels"], {})

    def test_metric_with_labels(self):
        """Test parsing metric with labels"""
        text = 'mysql_global_status_commands_total{command="select"} 12345'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(
            metrics[0]["metric_name"], "mysql_global_status_commands_total"
        )
        self.assertEqual(metrics[0]["value"], 12345.0)
        self.assertEqual(metrics[0]["labels"], {"command": "select"})

    def test_metric_with_multiple_labels(self):
        """Test parsing metric with multiple labels"""
        text = 'mysql_info_schema_table_rows{schema="test",table="users"} 1000'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["metric_name"], "mysql_info_schema_table_rows")
        self.assertEqual(metrics[0]["value"], 1000.0)
        self.assertEqual(metrics[0]["labels"], {"schema": "test", "table": "users"})

    def test_metric_with_help_and_type(self):
        """Test parsing metric with HELP and TYPE comments"""
        text = """# HELP mysql_global_status_threads_connected Number of currently open connections
# TYPE mysql_global_status_threads_connected gauge
mysql_global_status_threads_connected 42"""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(
            metrics[0]["metric_name"], "mysql_global_status_threads_connected"
        )
        self.assertEqual(metrics[0]["value"], 42.0)
        self.assertEqual(metrics[0]["metric_type"], "gauge")
        self.assertEqual(
            metrics[0]["metric_help"], "Number of currently open connections"
        )

    def test_multiple_metrics(self):
        """Test parsing multiple metrics"""
        text = """mysql_global_status_threads_connected 42
mysql_global_status_threads_running 5
mysql_global_status_uptime 86400"""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 3)
        self.assertEqual(metrics[0]["value"], 42.0)
        self.assertEqual(metrics[1]["value"], 5.0)
        self.assertEqual(metrics[2]["value"], 86400.0)

    def test_metric_with_float_value(self):
        """Test parsing metric with floating point value"""
        text = "mysql_global_status_innodb_buffer_pool_read_requests 123.456"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], 123.456)

    def test_metric_with_scientific_notation(self):
        """Test parsing metric with scientific notation"""
        text = "mysql_global_status_queries 1.23e6"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], 1230000.0)

    def test_empty_input(self):
        """Test parsing empty input"""
        text = ""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 0)

    def test_only_comments(self):
        """Test parsing input with only comments"""
        text = """# HELP mysql_up MySQL server availability
# TYPE mysql_up gauge"""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 0)

    def test_malformed_line_skipped(self):
        """Test that malformed lines are skipped gracefully"""
        text = """mysql_global_status_threads_connected 42
this_is_malformed_line
mysql_global_status_threads_running 5"""

        metrics = self.collector.parse_prometheus_format(text)

        # Should parse 2 valid metrics, skip the malformed one
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0]["value"], 42.0)
        self.assertEqual(metrics[1]["value"], 5.0)

    def test_labels_with_spaces(self):
        """Test parsing labels with spaces in values"""
        text = 'mysql_version_info{version="10.6.12-MariaDB"} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"version": "10.6.12-MariaDB"})

    def test_metric_with_timestamp(self):
        """Test parsing metric with timestamp (should extract value only)"""
        text = "mysql_global_status_threads_connected 42 1234567890"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], 42.0)

    def test_real_mariadb_metrics_sample(self):
        """Test parsing real MariaDB metrics sample"""
        text = """# HELP mysql_global_status_threads_connected Number of currently open connections
# TYPE mysql_global_status_threads_connected gauge
mysql_global_status_threads_connected 8
# HELP mysql_global_status_threads_running Number of threads executing queries
# TYPE mysql_global_status_threads_running gauge
mysql_global_status_threads_running 1
# HELP mysql_global_status_uptime Server uptime in seconds
# TYPE mysql_global_status_uptime counter
mysql_global_status_uptime 86400
# HELP mysql_info_schema_table_rows Number of rows in tables
# TYPE mysql_info_schema_table_rows gauge
mysql_info_schema_table_rows{schema="mysql",table="user"} 5
mysql_info_schema_table_rows{schema="test",table="data"} 1000"""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 5)

        # Check first metric
        self.assertEqual(
            metrics[0]["metric_name"], "mysql_global_status_threads_connected"
        )
        self.assertEqual(metrics[0]["value"], 8.0)
        self.assertEqual(metrics[0]["metric_type"], "gauge")

        # Check metric with labels
        self.assertEqual(metrics[3]["metric_name"], "mysql_info_schema_table_rows")
        self.assertEqual(metrics[3]["labels"]["schema"], "mysql")
        self.assertEqual(metrics[3]["labels"]["table"], "user")
        self.assertEqual(metrics[3]["value"], 5.0)

    def test_maxscale_metrics_sample(self):
        """Test parsing MaxScale metrics"""
        text = """# HELP maxscale_server_connections Current connections to server
# TYPE maxscale_server_connections gauge
maxscale_server_connections{server="server1",state="Master"} 10
maxscale_server_connections{server="server2",state="Slave"} 5"""

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0]["labels"]["server"], "server1")
        self.assertEqual(metrics[0]["labels"]["state"], "Master")
        self.assertEqual(metrics[1]["labels"]["server"], "server2")

    def test_metric_name_with_underscores(self):
        """Test metric names with multiple underscores"""
        text = "mysql_global_status_innodb_buffer_pool_read_requests 12345"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(
            metrics[0]["metric_name"],
            "mysql_global_status_innodb_buffer_pool_read_requests",
        )

    def test_zero_value(self):
        """Test parsing metric with zero value"""
        text = "mysql_global_status_slow_queries 0"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], 0.0)

    def test_negative_value(self):
        """Test parsing metric with negative value"""
        text = "mysql_global_status_some_metric -123"

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["value"], -123.0)

    def test_labels_with_special_characters(self):
        """Test labels with special characters"""
        text = 'mysql_table_info{schema="test-db",table="user_data"} 100'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"]["schema"], "test-db")
        self.assertEqual(metrics[0]["labels"]["table"], "user_data")


class TestHECTransformation(unittest.TestCase):
    """Test transformation to Splunk HEC format"""

    def setUp(self):
        """Set up test environment"""
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"

        self.collector = MetricsCollector()

    def test_transform_simple_metric(self):
        """Test transforming simple metric to HEC format"""
        metrics = [
            {
                "metric_name": "mysql_global_status_threads_connected",
                "value": 42.0,
                "labels": {},
                "metric_type": "gauge",
                "metric_help": "Number of connections",
            }
        ]

        events = self.collector.transform_to_hec_events(metrics)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "metric")
        self.assertEqual(events[0]["sourcetype"], "metrics")
        self.assertEqual(
            events[0]["fields"]["metric_name"],
            "mariadb.mysql_global_status_threads_connected",
        )
        self.assertEqual(events[0]["fields"]["_value"], 42.0)
        self.assertEqual(events[0]["fields"]["metric_type"], "gauge")

    def test_transform_metric_with_labels(self):
        """Test transforming metric with labels to HEC format"""
        metrics = [
            {
                "metric_name": "mysql_info_schema_table_rows",
                "value": 1000.0,
                "labels": {"schema": "test", "table": "users"},
                "metric_type": "gauge",
                "metric_help": None,
            }
        ]

        events = self.collector.transform_to_hec_events(metrics)

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["fields"]["metric_name"], "mariadb.mysql_info_schema_table_rows"
        )
        self.assertEqual(events[0]["fields"]["_value"], 1000.0)
        self.assertEqual(events[0]["fields"]["schema"], "test")
        self.assertEqual(events[0]["fields"]["table"], "users")
        self.assertEqual(events[0]["fields"]["metric_type"], "gauge")


if __name__ == "__main__":
    unittest.main()
