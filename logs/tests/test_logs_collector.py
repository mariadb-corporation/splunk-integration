#!/usr/bin/env python3
"""
Unit tests for the MariaDB Cloud logs collector (parsing, dedup, HEC transform).
"""

import io
import os
import sys
import json
import time
import zipfile
import unittest
from datetime import datetime
from unittest import mock

# Add scripts directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import mariadb_logs_collector as mod
from mariadb_logs_collector import MariaDBLogsCollector


def make_zip(filename: str, lines: list) -> bytes:
    """Build an in-memory zip archive of JSON-wrapped log lines.

    Mirrors the MariaDB Cloud archive format: each line is a JSON object with a
    "log" field containing the raw log text.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        body = "\n".join(json.dumps({"log": line}) for line in lines)
        zf.writestr(filename, body)
    return buf.getvalue()


class BaseCollectorTest(unittest.TestCase):
    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        self.collector = MariaDBLogsCollector()


class TestParseLogArchive(BaseCollectorTest):
    def test_error_log_timestamp_and_level(self):
        lines = ["2026-01-09T00:31:43.123Z 0 [Warning] Something happened"]
        archive = make_zip("error.log", lines)

        log_lines, last_ts = self.collector.parse_log_archive(
            archive, log_type="error-log", last_timestamp=None
        )

        self.assertEqual(len(log_lines), 1)
        self.assertEqual(log_lines[0]["timestamp"], "2026-01-09T00:31:43.123Z")
        self.assertEqual(log_lines[0]["log.level"], "Warning")
        self.assertEqual(log_lines[0]["filename"], "error.log")
        self.assertEqual(last_ts, "2026-01-09T00:31:43.123Z")

    def test_audit_log_timestamp_parsing(self):
        # Audit log format: "YYYYMMDD HH:MM:SS,rest,of,record"
        lines = ["20260109 00:31:43,server,root,localhost"]
        archive = make_zip("audit.log", lines)

        log_lines, _ = self.collector.parse_log_archive(
            archive, log_type="audit-log", last_timestamp=None
        )

        self.assertEqual(len(log_lines), 1)
        self.assertEqual(log_lines[0]["timestamp"], "2026-01-09T00:31:43Z")
        self.assertEqual(log_lines[0]["log.level"], "INFO")

    def test_maxscale_log_level(self):
        lines = [
            "2026-01-09T00:31:43.198168478Z stdout F 2026-01-09 00:31:43   error  : boom"
        ]
        archive = make_zip("maxscale.log", lines)

        log_lines, _ = self.collector.parse_log_archive(
            archive, log_type="maxscale-log", last_timestamp=None
        )

        self.assertEqual(len(log_lines), 1)
        self.assertEqual(log_lines[0]["timestamp"], "2026-01-09T00:31:43.198168478Z")
        self.assertEqual(log_lines[0]["log.level"], "error")

    def test_dedup_skips_lines_strictly_older_than_last_timestamp(self):
        # Dedup uses strict "<": lines older than last_timestamp are dropped,
        # while the boundary line (equal to last_timestamp) is retained. This
        # yields at-least-once semantics at the boundary.
        lines = [
            "2026-01-09T00:00:01.000Z 0 [Note] old line",
            "2026-01-09T00:00:02.000Z 0 [Note] boundary line",
            "2026-01-09T00:00:03.000Z 0 [Note] new line",
        ]
        archive = make_zip("error.log", lines)

        log_lines, last_ts = self.collector.parse_log_archive(
            archive,
            log_type="error-log",
            last_timestamp="2026-01-09T00:00:02.000Z",
        )

        # "old line" dropped; "boundary line" and "new line" retained.
        self.assertEqual(len(log_lines), 2)
        self.assertIn("boundary line", log_lines[0]["message"])
        self.assertIn("new line", log_lines[1]["message"])
        self.assertEqual(last_ts, "2026-01-09T00:00:03.000Z")

    def test_bad_zip_returns_empty(self):
        log_lines, last_ts = self.collector.parse_log_archive(
            b"not a zip", log_type="error-log", last_timestamp=None
        )
        self.assertEqual(log_lines, [])
        self.assertIsNone(last_ts)

    def test_out_of_order_lines_are_not_dropped(self):
        # Regression: the returned timestamp must be the MAX seen, not the
        # last-processed line's timestamp. An earlier line appearing after a
        # later one must still be kept (and not silently dropped in-cycle).
        lines = [
            "2026-01-09T00:00:03.000Z 0 [Note] later line",
            "2026-01-09T00:00:01.000Z 0 [Note] earlier line",
        ]
        archive = make_zip("error.log", lines)

        log_lines, last_ts = self.collector.parse_log_archive(
            archive, log_type="error-log", last_timestamp=None
        )

        self.assertEqual(len(log_lines), 2)
        self.assertIn("earlier line", log_lines[1]["message"])
        # Returned checkpoint is the maximum, not the last line processed.
        self.assertEqual(last_ts, "2026-01-09T00:00:03.000Z")

    def test_continuation_line_inherits_previous_timestamp(self):
        # A line without its own parseable timestamp (e.g. a stack-trace
        # continuation) must inherit the previous line's timestamp instead of
        # getting a fresh utcnow() that would defeat dedup. It must also NOT
        # inherit the previous line's log level.
        lines = [
            "2026-01-09T00:00:05.000Z 0 [Error] boom",
            "        at some.stack.frame(line)",
        ]
        archive = make_zip("error.log", lines)

        log_lines, last_ts = self.collector.parse_log_archive(
            archive, log_type="error-log", last_timestamp=None
        )

        self.assertEqual(len(log_lines), 2)
        # #1: continuation inherits the parent timestamp (not utcnow()).
        self.assertEqual(log_lines[1]["timestamp"], "2026-01-09T00:00:05.000Z")
        # #7: level is reset per line, not carried over from the [Error] line.
        self.assertEqual(log_lines[0]["log.level"], "Error")
        self.assertEqual(log_lines[1]["log.level"], "INFO")
        self.assertEqual(last_ts, "2026-01-09T00:00:05.000Z")

    def test_non_dict_json_line_does_not_abort_file(self):
        # A JSON line that decodes to a non-dict (e.g. a bare number) must not
        # raise and abort parsing of the rest of the file.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "error.log",
                "42\n" + json.dumps({"log": "2026-01-09T00:00:01.000Z 0 [Note] ok"}),
            )
        log_lines, _ = self.collector.parse_log_archive(
            buf.getvalue(), log_type="error-log", last_timestamp=None
        )
        # The valid second line is still extracted.
        self.assertTrue(
            any(
                isinstance(ll["message"], str) and "ok" in ll["message"]
                for ll in log_lines
            )
        )


class TestHECTransform(BaseCollectorTest):
    def test_transform_shape_and_fields(self):
        log_lines = [
            {
                "filename": "error.log",
                "message": "boom",
                "timestamp": "2026-01-09T00:31:43.123Z",
                "log.level": "Error",
            }
        ]
        log_meta = {
            "server": "server-1",
            "service": "svc-1",
            "serverDataSourceId": "ds-1",
        }

        events = self.collector.transform_to_hec_events(
            log_lines, log_meta, "error-log"
        )

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["index"], "mariadb_logs")
        self.assertEqual(ev["sourcetype"], "mariadb:logs")
        self.assertEqual(ev["source"], "mariadb_logs_api")
        # time must be epoch seconds (float), not the ISO string
        self.assertIsInstance(ev["time"], float)
        self.assertEqual(ev["event"]["message"], "boom")
        self.assertEqual(ev["event"]["logType"], "error-log")
        self.assertEqual(ev["event"]["log.level"], "Error")
        self.assertEqual(ev["event"]["server"], "server-1")

    def test_iso_to_epoch_roundtrip(self):
        # 2026-01-09T00:00:00Z == 1767916800 epoch seconds (UTC)
        epoch = self.collector._iso_to_epoch("2026-01-09T00:00:00Z")
        self.assertAlmostEqual(epoch, 1767916800.0, places=3)

    def test_iso_to_epoch_nanosecond_precision(self):
        # Should not raise on >6 fractional digits; truncates to microseconds.
        epoch = self.collector._iso_to_epoch("2026-01-09T00:31:43.198168478Z")
        self.assertIsInstance(epoch, float)
        self.assertGreater(epoch, 0)

    def test_iso_to_epoch_fallback_on_garbage(self):
        before = time.time()
        epoch = self.collector._iso_to_epoch("not-a-timestamp")
        self.assertGreaterEqual(epoch, before)


class TestCheckpoint(BaseCollectorTest):
    def setUp(self):
        super().setUp()
        # Use an isolated checkpoint path per test run
        self.cp_path = os.path.join(
            os.path.dirname(__file__), "_test_checkpoint.json"
        )
        self.collector.checkpoint_file = self.cp_path

    def tearDown(self):
        if os.path.exists(self.cp_path):
            os.remove(self.cp_path)

    def test_save_prunes_entries_older_than_two_days(self):
        logs_stat = {
            "fresh": {"last_timestamp": "2026-01-12T10:00:00Z"},
            "stale": {"last_timestamp": "2026-01-08T10:00:00Z"},  # >2 days before start
        }
        self.collector.save_checkpoint(
            "2026-01-12T00:00:00Z", "2026-01-12T12:00:00Z", logs_stat
        )

        with open(self.cp_path) as f:
            saved = json.load(f)

        self.assertIn("fresh", saved["logs_stat"])
        self.assertNotIn("stale", saved["logs_stat"])

    def test_update_log_stat_inserts_and_updates(self):
        logs_stat = {}
        self.collector.update_log_stat(logs_stat, "id-1", "2026-01-12T10:00:00Z")
        self.assertEqual(
            logs_stat["id-1"]["last_timestamp"], "2026-01-12T10:00:00Z"
        )
        self.collector.update_log_stat(logs_stat, "id-1", "2026-01-12T11:00:00Z")
        self.assertEqual(
            logs_stat["id-1"]["last_timestamp"], "2026-01-12T11:00:00Z"
        )


class _FakeS3:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self):
        self.store = {}

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.store:
            err = Exception("not found")
            err.response = {"Error": {"Code": "NoSuchKey"}}
            raise err
        return {"Body": io.BytesIO(self.store[(Bucket, Key)])}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.store[(Bucket, Key)] = Body


class TestS3Checkpoint(BaseCollectorTest):
    """The checkpoint backend transparently uses S3 for s3:// locations."""

    def setUp(self):
        super().setUp()
        self.collector.checkpoint_file = "s3://my-bucket/mariadb/checkpoint.json"
        self.fake_s3 = _FakeS3()
        self.collector._s3 = self.fake_s3  # inject; bypasses lazy boto3 import

    def test_parse_s3_uri(self):
        self.assertEqual(
            self.collector._parse_s3_uri("s3://bucket/a/b/c.json"),
            ("bucket", "a/b/c.json"),
        )

    def test_parse_s3_uri_rejects_missing_key(self):
        with self.assertRaises(ValueError):
            self.collector._parse_s3_uri("s3://bucket-only")

    def test_load_missing_object_returns_empty(self):
        # No object stored yet (first run) -> empty checkpoint, not an error.
        self.assertEqual(self.collector.load_checkpoint(), {"logs_stat": {}})

    def test_save_then_load_roundtrip_via_s3(self):
        logs_stat = {"id-1": {"last_timestamp": "2026-01-12T10:00:00Z"}}
        self.collector.save_checkpoint(
            "2026-01-12T00:00:00Z", "2026-01-12T12:00:00Z", logs_stat
        )

        # Data landed in S3, not on the local filesystem.
        self.assertIn(("my-bucket", "mariadb/checkpoint.json"), self.fake_s3.store)
        self.assertFalse(os.path.exists(self.collector.checkpoint_file))

        loaded = self.collector.load_checkpoint()
        self.assertEqual(
            loaded["logs_stat"]["id-1"]["last_timestamp"], "2026-01-12T10:00:00Z"
        )


class TestRuntimeDeadline(BaseCollectorTest):
    """The soft runtime deadline stops the cycle gracefully between archives."""

    def test_compute_deadline_default(self):
        budget = mod._compute_deadline(None) - time.monotonic()
        self.assertAlmostEqual(budget, 180, delta=2)

    def test_compute_deadline_capped_by_context(self):
        class Ctx:
            def get_remaining_time_in_millis(self):
                return 60_000  # 60s remaining -> 60 - 30 buffer = 30s budget

        budget = mod._compute_deadline(Ctx()) - time.monotonic()
        self.assertAlmostEqual(budget, 30, delta=2)

    def test_deadline_reached_helper(self):
        self.collector._deadline = None
        self.assertFalse(self.collector._deadline_reached())
        self.collector._deadline = time.monotonic() - 1
        self.assertTrue(self.collector._deadline_reached())

    def test_run_stops_gracefully_at_deadline(self):
        # One page with one archive available, but the deadline is already past.
        self.collector.load_checkpoint = lambda: {"logs_stat": {}}
        self.collector.fetch_servers = lambda: {}
        self.collector.fetch_log_metadata = mock.Mock(
            return_value={
                "logs": [{"id": "1", "logType": "error-log", "name": "error.log"}],
                "count": 1,
            }
        )
        self.collector.fetch_log_archive = mock.Mock()
        self.collector.send_to_splunk_hec = mock.Mock(return_value=True)

        rc = self.collector.run(deadline=time.monotonic() - 1)

        # Clean early exit (0, not a failure); no archive fetched or sent.
        self.assertEqual(rc, 0)
        self.collector.fetch_log_archive.assert_not_called()
        self.collector.send_to_splunk_hec.assert_not_called()

    def test_checkpoint_persisted_for_sent_archives_before_deadline_exit(self):
        """The archive sent before the deadline must be in the checkpoint on exit."""
        cp_path = os.path.join(os.path.dirname(__file__), "_deadline_checkpoint.json")
        self.collector.checkpoint_file = cp_path  # real local save/load
        # Recent timestamp so save_checkpoint's 2-day prune keeps the entry.
        recent = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        try:
            self.collector.fetch_servers = lambda: {}
            # Two archives in one page: a1 processed, then the deadline hits at a2.
            self.collector.fetch_log_metadata = mock.Mock(
                return_value={
                    "logs": [
                        {"id": "a1", "logType": "error-log", "name": "e1.log"},
                        {"id": "a2", "logType": "error-log", "name": "e2.log"},
                    ],
                    "count": 2,
                }
            )
            self.collector.fetch_log_archive = mock.Mock(return_value=b"zip")
            self.collector.parse_log_archive = mock.Mock(
                return_value=(
                    [{"message": "x", "timestamp": recent, "filename": "e1.log",
                      "log.level": "INFO"}],
                    recent,
                )
            )
            self.collector.transform_to_hec_events = mock.Mock(
                return_value=[{"event": "x"}]
            )
            self.collector.send_to_splunk_hec = mock.Mock(return_value=True)
            # Not reached for archive #1, reached before archive #2.
            self.collector._deadline_reached = mock.Mock(side_effect=[False, True])

            rc = self.collector.run(deadline=time.monotonic() + 1000)

            self.assertEqual(rc, 0)
            # Exactly one archive sent (a1); a2 was skipped by the deadline.
            self.assertEqual(self.collector.send_to_splunk_hec.call_count, 1)

            # The checkpoint file exists and records a1 (sent) but not a2 (skipped).
            self.assertTrue(os.path.exists(cp_path))
            with open(cp_path) as f:
                saved = json.load(f)
            self.assertIn("a1", saved["logs_stat"])
            self.assertNotIn("a2", saved["logs_stat"])
            self.assertEqual(saved["logs_stat"]["a1"]["last_timestamp"], recent)
        finally:
            if os.path.exists(cp_path):
                os.remove(cp_path)

    def test_deadline_ignored_for_interactive_daemon_run(self):
        """run() without a deadline (interactive/daemon) never stops early,
        even if MAX_RUNTIME_SECONDS is set in the environment."""
        os.environ["MAX_RUNTIME_SECONDS"] = "1"  # tiny; must have NO effect here
        recent = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        try:
            self.collector.load_checkpoint = lambda: {"logs_stat": {}}
            self.collector.save_checkpoint = mock.Mock()
            self.collector.fetch_servers = lambda: {}
            self.collector.fetch_log_metadata = mock.Mock(
                return_value={
                    "logs": [
                        {"id": "a1", "logType": "error-log", "name": "e1.log"},
                        {"id": "a2", "logType": "error-log", "name": "e2.log"},
                    ],
                    "count": 2,
                }
            )
            self.collector.fetch_log_archive = mock.Mock(return_value=b"zip")
            self.collector.parse_log_archive = mock.Mock(
                return_value=([{"message": "x", "timestamp": recent}], recent)
            )
            self.collector.transform_to_hec_events = mock.Mock(
                return_value=[{"event": "x"}]
            )
            self.collector.send_to_splunk_hec = mock.Mock(return_value=True)

            # Called exactly as main()/run_daemon() do: no deadline argument.
            rc = self.collector.run()

            self.assertEqual(rc, 0)
            self.assertIsNone(self.collector._deadline)
            # BOTH archives sent: the deadline logic did not kick in.
            self.assertEqual(self.collector.send_to_splunk_hec.call_count, 2)
        finally:
            os.environ.pop("MAX_RUNTIME_SECONDS", None)


class TestLambdaHandler(unittest.TestCase):
    """lambda_handler runs one cycle and raises on failure."""

    def setUp(self):
        os.environ["MARIADB_API_KEY"] = "test-key"
        os.environ["SPLUNK_HEC_URL"] = "https://test.splunkcloud.com:8088"
        os.environ["SPLUNK_HEC_TOKEN"] = "test-token"
        os.environ.pop("SECRETS_ARN", None)  # no Secrets Manager -> no boto3 needed

    def test_success_returns_ok(self):
        with mock.patch.object(mod.MariaDBLogsCollector, "run", lambda self, deadline=None: 0):
            self.assertEqual(mod.lambda_handler({}, None), {"status": "ok"})

    def test_failure_raises(self):
        with mock.patch.object(mod.MariaDBLogsCollector, "run", lambda self, deadline=None: 1):
            with self.assertRaises(RuntimeError):
                mod.lambda_handler({}, None)


class TestDaemonInterval(unittest.TestCase):
    """Test that run_daemon enforces the minimum polling interval (5 min)."""

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
            # Request shutdown on the 2nd cycle so the 1st cycle's between-cycle
            # sleep executes and can be observed, then the loop ends.
            if state["runs"] >= 2:
                mod.shutdown_requested = True
            return 0

        with mock.patch.object(
            mod.MariaDBLogsCollector, "run", fake_run
        ), mock.patch.object(
            mod.time, "sleep", lambda secs: sleeps.append(secs)
        ), mock.patch.object(mod.signal, "signal"):
            mod.run_daemon(interval=interval)

        return sleeps, state["runs"]

    def test_sub_minimum_interval_is_clamped(self):
        """An interval below MIN_INTERVAL must be raised to MIN_INTERVAL."""
        sleeps, runs = self._run_daemon_capturing_sleeps(interval=60)

        # One completed cycle sleeps MIN_INTERVAL x 1s (clamped up from 60).
        self.assertEqual(sleeps, [1] * mod.MIN_INTERVAL)
        self.assertNotIn(0, sleeps)
        self.assertEqual(runs, 2)

    def test_at_minimum_interval_preserved(self):
        """The default 300s interval is at the minimum and is preserved."""
        sleeps, runs = self._run_daemon_capturing_sleeps(interval=mod.MIN_INTERVAL)

        self.assertEqual(sleeps, [1] * mod.MIN_INTERVAL)
        self.assertEqual(runs, 2)


if __name__ == "__main__":
    unittest.main()
