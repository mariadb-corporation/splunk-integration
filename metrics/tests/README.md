# Unit Tests for MariaDB Metrics Integration

This directory contains unit tests for the MariaDB Cloud metrics integration.

## Test Coverage

### Prometheus Parser Tests (`test_metrics_collector.py`)

Comprehensive tests for Prometheus format parsing:

**Basic Parsing:**
- Simple metrics without labels
- Metrics with single label
- Metrics with multiple labels
- Metrics with HELP and TYPE comments
- Multiple metrics in one response

**Value Types:**
- Integer values
- Floating point values
- Scientific notation
- Zero values
- Negative values

**Edge Cases:**
- Empty input
- Only comments (no metrics)
- Malformed lines (should be skipped gracefully)
- Metrics with timestamps
- Labels with special characters
- Labels with spaces in values

**Real-World Scenarios:**
- Real MariaDB metrics samples
- MaxScale metrics samples
- Metric names with multiple underscores

**HEC Transformation:**
- Simple metric transformation to Splunk HEC format
- Metric with labels transformation
- Correct field naming and structure

## Running Tests

### Run all tests:
```bash
python3 metrics/tests/test_metrics_collector.py
```

### Run with verbose output:
```bash
python3 metrics/tests/test_metrics_collector.py -v
```

### Run specific test:
```bash
python3 metrics/tests/test_metrics_collector.py TestPrometheusParser.test_simple_metric_without_labels
```

### Run from repository root:
```bash
cd /path/to/splunk-integration
python3 -m pytest metrics/tests/test_metrics_collector.py -v
```

## Test Results

All 20 tests should pass:
- 18 Prometheus parsing tests
- 2 HEC transformation tests

## Adding New Tests

When adding new test cases:

1. **Test real-world scenarios** - Use actual Prometheus output from MariaDB/MaxScale
2. **Test edge cases** - Empty values, special characters, malformed input
3. **Test error handling** - Ensure parser doesn't crash on bad input
4. **Update this README** - Document new test coverage

## Dependencies

Tests require:
- Python 3.7+
- `requests` library (for MetricsCollector import)

No additional test frameworks required - uses Python's built-in `unittest`.
