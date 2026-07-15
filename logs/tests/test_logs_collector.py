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

# Add scripts directory to path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

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


if __name__ == "__main__":
    unittest.main()
