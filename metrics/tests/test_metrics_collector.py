#!/usr/bin/env python3
"""
Unit tests for Prometheus format parser in MariaDB metrics collector
"""

import unittest
import sys
import os
import time
from unittest import mock

# Add parent directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import mariadb_metrics_collector as mod
from mariadb_metrics_collector import MetricsCollector


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

    def test_label_value_with_closing_brace(self):
        """A '}' inside a quoted label value must not truncate parsing."""
        text = 'mysql_info{version="10.6}beta"} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"version": "10.6}beta"})
        self.assertEqual(metrics[0]["value"], 1.0)

    def test_label_value_with_closing_brace_and_more_labels(self):
        """A '}' in one value still lets later labels and the value parse."""
        text = 'mysql_info{a="x}y",b="z"} 42'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"a": "x}y", "b": "z"})
        self.assertEqual(metrics[0]["value"], 42.0)

    def test_label_value_with_escaped_backslash(self):
        """Escaped backslashes decode to a single backslash (\\\\ -> \\)."""
        text = r'mysql_file{path="C:\\logs"} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"path": "C:\\logs"})

    def test_label_value_with_escaped_quote(self):
        """An escaped quote is decoded and does not end the value early."""
        text = r'mysql_msg{text="say \"hi\""} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"text": 'say "hi"'})
        self.assertEqual(metrics[0]["value"], 1.0)

    def test_label_value_with_escaped_newline(self):
        """An escaped newline (\\n) is decoded to a real newline."""
        text = r'mysql_msg{text="line1\nline2"} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"text": "line1\nline2"})

    def test_label_value_with_comma(self):
        """A comma inside a quoted value is not treated as a label separator."""
        text = 'mysql_info{list="a,b,c",count="2"} 1'

        metrics = self.collector.parse_prometheus_format(text)

        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["labels"], {"list": "a,b,c", "count": "2"})


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


class TestConfigValidation(unittest.TestCase):
    """Test numeric env-var parsing and validation in __init__"""

    NUMERIC_VARS = (
        "METRICS_BATCH_SIZE",
        "METRICS_MAX_RETRIES",
        "METRICS_RETRY_DELAY",
    )

    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        for var in self.NUMERIC_VARS:
            os.environ.pop(var, None)

    def tearDown(self):
        for var in self.NUMERIC_VARS:
            os.environ.pop(var, None)

    def test_defaults_when_unset(self):
        """Unset numeric vars fall back to their defaults."""
        collector = MetricsCollector()
        self.assertEqual(collector.batch_size, 1000)
        self.assertEqual(collector.max_retries, 3)
        self.assertEqual(collector.retry_delay, 5)

    def test_valid_numeric_env_parsed(self):
        """A valid numeric override is applied."""
        os.environ["METRICS_BATCH_SIZE"] = "250"
        collector = MetricsCollector()
        self.assertEqual(collector.batch_size, 250)

    def test_non_numeric_env_raises_clear_error(self):
        """A non-numeric value fails fast with a message naming the var."""
        os.environ["METRICS_BATCH_SIZE"] = "1oo"
        with self.assertRaises(ValueError) as ctx:
            MetricsCollector()
        self.assertIn("METRICS_BATCH_SIZE", str(ctx.exception))

    def test_whitespace_padded_value_still_parses(self):
        """int() tolerates surrounding whitespace, so this must still work."""
        os.environ["METRICS_BATCH_SIZE"] = " 100 "
        collector = MetricsCollector()
        self.assertEqual(collector.batch_size, 100)

    def test_zero_batch_size_rejected(self):
        """batch_size must be >= 1 (a 0 batch would send nothing)."""
        os.environ["METRICS_BATCH_SIZE"] = "0"
        with self.assertRaises(ValueError):
            MetricsCollector()

    def test_negative_retry_delay_rejected(self):
        """retry_delay must be >= 0."""
        os.environ["METRICS_RETRY_DELAY"] = "-1"
        with self.assertRaises(ValueError):
            MetricsCollector()


class TestDaemonInterval(unittest.TestCase):
    """Test that run_daemon guards against a zero/negative interval"""

    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        mod.shutdown_requested = False

    def tearDown(self):
        mod.shutdown_requested = False

    def _run_daemon_capturing_sleeps(self, interval):
        """Run run_daemon with run()/sleep/signal mocked; return sleep args."""
        state = {"runs": 0}
        sleeps = []

        def fake_run(_self):
            state["runs"] += 1
            # Request shutdown on the 2nd cycle so the between-cycle sleep of
            # the 1st cycle executes and can be observed, then the loop ends.
            if state["runs"] >= 2:
                mod.shutdown_requested = True
            return 0

        with mock.patch.object(mod.MetricsCollector, "run", fake_run), mock.patch.object(
            mod.time, "sleep", lambda secs: sleeps.append(secs)
        ), mock.patch.object(mod.signal, "signal"):
            mod.run_daemon(interval=interval)

        return sleeps, state["runs"]

    def test_sub_minimum_interval_is_clamped(self):
        """An interval below MIN_INTERVAL must be raised to MIN_INTERVAL."""
        sleeps, runs = self._run_daemon_capturing_sleeps(interval=0)

        # One completed cycle sleeps MIN_INTERVAL x 1s, all increments 1s
        # (clamped), never 0s — no busy loop.
        self.assertEqual(sleeps, [1] * mod.MIN_INTERVAL)
        self.assertNotIn(0, sleeps)
        # Only the two cycles we allowed ran — no runaway looping.
        self.assertEqual(runs, 2)

    def test_positive_interval_preserved(self):
        """An interval at/above MIN_INTERVAL sleeps in 1s increments up to it."""
        interval = mod.MIN_INTERVAL + 15
        sleeps, runs = self._run_daemon_capturing_sleeps(interval=interval)

        # One completed cycle sleeps `interval` x 1s before the ending cycle.
        self.assertEqual(sleeps, [1] * interval)
        self.assertEqual(runs, 2)


class _FakeContext:
    """Stand-in for the Lambda context object."""

    def __init__(self, remaining_ms):
        self._remaining_ms = remaining_ms

    def get_remaining_time_in_millis(self):
        return self._remaining_ms


class TestRuntimeDeadline(unittest.TestCase):
    """The soft runtime deadline halts sending before the Lambda hard timeout."""

    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        os.environ.pop("MAX_RUNTIME_SECONDS", None)

    def tearDown(self):
        os.environ.pop("MAX_RUNTIME_SECONDS", None)

    def test_deadline_defaults_to_270(self):
        # No context -> falls back to the 270s default budget.
        budget = mod._compute_deadline(None) - time.monotonic()
        self.assertAlmostEqual(budget, 270, delta=2)

    def test_deadline_capped_by_context_remaining(self):
        # 300s timeout: 270 default is under (remaining - 30s buffer) = 270.
        budget = mod._compute_deadline(_FakeContext(300_000)) - time.monotonic()
        self.assertAlmostEqual(budget, 270, delta=2)

    def test_short_timeout_shrinks_budget(self):
        # 60s remaining -> capped to 60 - 30 = 30s, below the 270 default.
        budget = mod._compute_deadline(_FakeContext(60_000)) - time.monotonic()
        self.assertAlmostEqual(budget, 30, delta=2)

    def test_env_override_respected(self):
        os.environ["MAX_RUNTIME_SECONDS"] = "100"
        budget = mod._compute_deadline(_FakeContext(600_000)) - time.monotonic()
        self.assertAlmostEqual(budget, 100, delta=2)

    def test_deadline_reached_helper(self):
        c = MetricsCollector()
        c._deadline = None
        self.assertFalse(c._deadline_reached())
        c._deadline = time.monotonic() + 100
        self.assertFalse(c._deadline_reached())
        c._deadline = time.monotonic() - 1
        self.assertTrue(c._deadline_reached())

    def test_send_stops_at_deadline_without_http(self):
        c = MetricsCollector()
        c._deadline = time.monotonic() - 1  # already past
        with mock.patch.object(mod.requests, "post") as post:
            result = c.send_to_splunk_hec([{"event": "metric"}])
        # Clean early stop (not a failure) and no HTTP was attempted.
        self.assertTrue(result)
        post.assert_not_called()

    def test_deadline_ignored_for_interactive_daemon_run(self):
        """With no deadline (interactive/daemon), MAX_RUNTIME_SECONDS has no
        effect and every batch is sent."""
        os.environ["MAX_RUNTIME_SECONDS"] = "1"  # tiny; must NOT apply here
        try:
            c = MetricsCollector()
            c.batch_size = 1
            c._deadline = None  # the state run() sets when called without a deadline
            events = [{"event": f"e{i}"} for i in range(3)]
            ok = mock.Mock(status_code=200)
            ok.json.return_value = {"code": 0}
            with mock.patch.object(mod.requests, "post", return_value=ok) as post:
                result = c.send_to_splunk_hec(events)
            self.assertTrue(result)
            # All three batches sent: the deadline logic never engaged.
            self.assertEqual(post.call_count, 3)
        finally:
            os.environ.pop("MAX_RUNTIME_SECONDS", None)


class TestLambdaHandler(unittest.TestCase):
    """lambda_handler runs one cycle and raises on failure."""

    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        os.environ.pop("SECRETS_ARN", None)  # no Secrets Manager -> no boto3 needed
        mod._secrets_loaded = False

    def test_success_returns_ok(self):
        with mock.patch.object(mod.MetricsCollector, "run", lambda self, deadline=None: 0):
            self.assertEqual(mod.lambda_handler({}, None), {"status": "ok"})

    def test_failure_raises(self):
        with mock.patch.object(mod.MetricsCollector, "run", lambda self, deadline=None: 1):
            with self.assertRaises(RuntimeError):
                mod.lambda_handler({}, None)

    def test_secrets_loader_noop_without_arn(self):
        # With SECRETS_ARN unset, the loader must not touch boto3 at all.
        mod._load_secrets_from_manager()  # would raise if it tried to import/use boto3


class TestSecretsLoader(unittest.TestCase):
    """_load_secrets_from_manager injects secret env vars without clobbering."""

    def setUp(self):
        os.environ["SECRETS_ARN"] = "arn:aws:secretsmanager:us-east-1:1:secret:x"
        mod._secrets_loaded = False
        for key in ("MARIADB_API_KEY", "SPLUNK_HEC_TOKEN"):
            os.environ.pop(key, None)

    def tearDown(self):
        os.environ.pop("SECRETS_ARN", None)
        mod._secrets_loaded = False

    def _patched_boto3(self, secret_string):
        """Return a fake boto3 module whose SM client yields secret_string."""
        fake_client = mock.Mock()
        fake_client.get_secret_value.return_value = {"SecretString": secret_string}
        fake_boto3 = mock.Mock()
        fake_boto3.client.return_value = fake_client
        return fake_boto3

    def test_injects_secret_values(self):
        fake_boto3 = self._patched_boto3(
            '{"MARIADB_API_KEY": "real-key", "SPLUNK_HEC_TOKEN": "real-token"}'
        )
        with mock.patch.dict("sys.modules", {"boto3": fake_boto3}):
            mod._load_secrets_from_manager()
        self.assertEqual(os.environ["MARIADB_API_KEY"], "real-key")
        self.assertEqual(os.environ["SPLUNK_HEC_TOKEN"], "real-token")

    def test_existing_env_var_is_not_clobbered(self):
        os.environ["MARIADB_API_KEY"] = "explicit-key"
        fake_boto3 = self._patched_boto3('{"MARIADB_API_KEY": "secret-key"}')
        with mock.patch.dict("sys.modules", {"boto3": fake_boto3}):
            mod._load_secrets_from_manager()
        # Explicit env var wins over the secret value.
        self.assertEqual(os.environ["MARIADB_API_KEY"], "explicit-key")

    def test_invalid_json_raises(self):
        fake_boto3 = self._patched_boto3("not-json")
        with mock.patch.dict("sys.modules", {"boto3": fake_boto3}):
            with self.assertRaises(ValueError):
                mod._load_secrets_from_manager()


if __name__ == "__main__":
    unittest.main()
