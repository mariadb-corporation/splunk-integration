# Copyright (c) 2026 MariaDB plc. All rights reserved.
#
# This software is intended for use by MariaDB subscription customers only.
# Unauthorized modification, copying or distribution is prohibited.
# MariaDB product terms at https://mariadb.com/terms/ apply.

"""
SkySQL Logs API Input Script for Splunk Universal Forwarder
Polls the SkySQL Logs API and outputs logs in JSON format for Splunk ingestion
"""

import sys
import json
import requests
import time
from datetime import datetime, timedelta
import os
import io
import zipfile
import re
import configparser

# Configuration
API_BASE_URL = os.environ.get('SKYSQL_API_URL', 'https://api.skysql.com')
API_KEY = os.environ.get('SKYSQL_API_KEY', '')
CHECKPOINT_FILE = os.environ.get('CHECKPOINT_FILE', '/opt/splunkforwarder/var/lib/splunk/skysql_checkpoint.json')

# App configuration
SPLUNK_HOME = os.environ.get('SPLUNK_HOME', '/opt/splunkforwarder')
APP_NAME = os.environ.get('APP_NAME', 'splunk-skysql-integration')
INPUTS_CONF_PATH = os.path.join(
    SPLUNK_HOME,
    'etc',
    'apps',
    APP_NAME,
    'default',
    'inputs.conf',
)


def load_interval_from_inputs_conf(default_interval=60):
    """Read the interval value from the app's default/inputs.conf using configparser.

    This allows the script's internal polling interval to stay in sync with
    the scripted input configuration. Falls back to default_interval on any
    error or if the setting is not found.
    """
    try:
        if not os.path.exists(INPUTS_CONF_PATH):
            return default_interval

        parser = configparser.ConfigParser()
        # Preserve case of keys and avoid interpolation surprises
        parser.optionxform = str
        read_files = parser.read(INPUTS_CONF_PATH)
        if not read_files:
            return default_interval

        # Find the stanza that corresponds to the scripted input wrapper
        target_section = None
        for section in parser.sections():
            if 'skysql_logs_wrapper.sh' in section:
                target_section = section
                break

        if not target_section:
            return default_interval

        section = parser[target_section]
        # Interval is typically stored as "interval = <seconds>"
        if 'interval' not in section:
            return default_interval

        try:
            interval = int(section['interval'])
            return interval
        except ValueError:
            # Malformed value; fall back to default
            return default_interval

    except Exception as e:
        print(f"WARNING: Failed to read interval from {INPUTS_CONF_PATH}: {e}", file=sys.stderr)
        return default_interval

# API Endpoints
LOGS_ENDPOINT = f"{API_BASE_URL}/observability/v2/logs"
LOGS_QUERY_ENDPOINT = f"{API_BASE_URL}/observability/v2/logs/query"
LOGS_ARCHIVE_ENDPOINT = f"{API_BASE_URL}/observability/v2/logs/archive"
LOGS_SERVERS_ENDPOINT = f"{API_BASE_URL}/observability/v2/logs/servers"

def load_checkpoint():
    """Load the last successful run timestamp"""
    try:
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, 'r') as f:
                checkpoint = json.load(f)
                return checkpoint
    except Exception as e:
        print(f"ERROR: Failed to load checkpoint: {e}", file=sys.stderr)

    from_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    to_date = datetime.utcnow().isoformat() + 'Z'
    return {'startTime': from_date, 'endTime': to_date, 'logs_stat': {}}

def save_checkpoint(startTime, endTime, logs_stat):
    """Save the current run timestamp"""

    global CHECKPOINT_FILE
    try:
        # Before persisting, remove any log_ids whose last_timestamp is
        # more than 2 days older than startTime to keep the checkpoint small.
        try:
            start_str = (startTime or '').rstrip('Z')
            if start_str:
                start_dt = datetime.fromisoformat(start_str)
                cutoff = start_dt - timedelta(days=2)

                to_delete = []
                for lid, info in list(logs_stat.items()):
                    ts_str = (info or {}).get('last_timestamp')
                    if not ts_str:
                        continue

                    ts_clean = str(ts_str).rstrip('Z')
                    try:
                        ts_dt = datetime.fromisoformat(ts_clean)
                    except ValueError:
                        # Malformed timestamps are ignored for pruning
                        continue

                    if ts_dt < cutoff:
                        to_delete.append(lid)

                for lid in to_delete:
                    del logs_stat[lid]
        except Exception as prune_err:
            print(f"WARNING: Failed to prune stale log_stat entries before checkpoint save: {prune_err}", file=sys.stderr)

        if os.path.dirname(CHECKPOINT_FILE):
            os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)

        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump({'startTime': startTime, 'endTime': endTime, 'logs_stat': logs_stat}, f)
    except Exception as e:
        print(f"ERROR: Failed to save checkpoint: {e}", file=sys.stderr)

def fetch_servers():
    """
    Fetch list of servers from SkySQL Logs API
    """
    headers = {
        'X-API-KEY': API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(LOGS_SERVERS_ENDPOINT, headers=headers, timeout=30)
        response.raise_for_status()
        servers = response.json()
        # Create serverContext using serverDataSourceId from the response
        serverContext = []
        for server in servers.get('servers', []):
            serverContext.append(server['serverDataSourceId'])
        return serverContext
    except Exception as e:
        print(f"ERROR: Failed to fetch servers: {e}", file=sys.stderr)
        return []

def fetch_log_metadata(from_date, to_date, limit=1000, offset=0):
    """
    Fetch log metadata from SkySQL Logs API
    
    Args:
        from_date: Start date in ISO format
        to_date: End date in ISO format
        limit: Maximum number of logs to return
        offset: Number of logs to skip
    
    Returns:
        dict: Response containing log metadata
    """
    headers = {
        'X-API-KEY': API_KEY,
        'Content-Type': 'application/json'
    }
    # fetch serverContext
    serverContext = fetch_servers()
    
    # Using POST /observability/v2/logs/query for more flexible querying
    payload = {
        'fromDate': from_date,
        'toDate': to_date,
        'limit': limit,
        'offset': offset,
        'logTypes': ["error-log", "audit-log", "maxscale-log"],
        'orderByField': 'startTime',
        'orderByDirection': 'asc',
        'serverContext': serverContext
    }
    
    try:
        response = requests.post(LOGS_QUERY_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        # print(response.json(), file=sys.stderr)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed: {e}", file=sys.stderr)
        return None

def fetch_log_archive(log_id, log_format='json'):
    """
    Fetch log archive from SkySQL Logs API
    
    Args:
        log_ids: Comma-separated string of log IDs or list of log IDs
        log_format: Format of the archive (default: json)
    
    Returns:
        bytes: Archive file content or None if failed
    """
    headers = {
        'X-API-KEY': API_KEY
    }
    
    params = {
        'logIds': log_id,
        'logFormat': log_format
    }
    
    try:
        response = requests.get(LOGS_ARCHIVE_ENDPOINT, headers=headers, params=params, timeout=60, stream=True)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch archive for log ID {log_id}: {e}", file=sys.stderr)
        return None

def parse_log_archive(archive_content, log_type='error-log', last_timestamp=None):
    """
    Parse log archive and extract individual log lines
    
    Args:
        archive_content: Bytes content of the archive file (zip format)
    
    Returns:
        list: List of log line dictionaries
    """
    log_lines = []
    file_name = None
    skipped_logs = 0
    log_level = 'INFO'
    try:
        # Open as zip file
        with zipfile.ZipFile(io.BytesIO(archive_content)) as zip_file:
            for file_info in zip_file.filelist:
                # Skip directories
                if file_info.is_dir():
                    continue
                
                try:
                    # Read file content
                    with zip_file.open(file_info) as file_obj:
                        content = file_obj.read()
                        try:
                            file_name = file_info.filename
                            # print(f"INFO: Processing file {file_name}, last timestamp {last_timestamp}", file=sys.stderr)
                            # Try to decode as text
                            text_content = content.decode('utf-8')
                            for line in text_content.splitlines():
                                message = line.strip()
                                if message:
                                    try:
                                        msg = json.loads(message)
                                        raw_message = msg.get('log', msg)
                                        message = raw_message

                                        if isinstance(message, str):
                                            if log_type == 'audit-log':
                                                parts = message.split(',', 1)
                                                if parts:
                                                    ts_str = parts[0]
                                                    try:
                                                        dt = datetime.strptime(ts_str, "%Y%m%d %H:%M:%S")
                                                        timestamp = dt.isoformat() + 'Z'
                                                        log_level = 'INFO'
                                                    except ValueError:
                                                        pass
                                            elif log_type in ('error-log', 'maxscale-log'):
                                                m_ts = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)', message)
                                                if m_ts:
                                                    timestamp = m_ts.group(1)
                                            if log_type == 'error-log':
                                                m_level = re.search(r'\[(\w+)\]', message)
                                                if m_level:
                                                    log_level = m_level.group(1)
                                            elif log_type in ('maxscale-log'):
                                                # Example:
                                                # 2026-01-09T00:31:43.198168478Z stdout F 2026-01-09 00:31:43   error  : (..)
                                                m_level = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+(\w+)\s*:',message)  
                                                if m_level:
                                                    log_level = m_level.group(1)
                                        if not timestamp:
                                            timestamp = datetime.utcnow().isoformat() + 'Z'

                                        if last_timestamp and timestamp < last_timestamp:
                                            skipped_logs += 1
                                            continue

                                        last_timestamp = timestamp                                     
                                    except ValueError:
                                        print(f"WARNING: Could not parse message as JSON: {message}", file=sys.stderr)
                                        timestamp = datetime.utcnow().isoformat() + 'Z'
                                        log_level = None
                                            
                                    log_lines.append({
                                        'filename': file_name,
                                        'message': message,
                                        'timestamp': timestamp,
                                        'log.level': log_level
                                    })
                                else:
                                    print(f"Empty log message found", file=sys.stderr)
                        except UnicodeDecodeError:
                            print(f"WARNING: Could not decode file {file_info.filename} as UTF-8", file=sys.stderr)
                except Exception as e:
                    print(f"WARNING: Failed to read file {file_info.filename}: {e}", file=sys.stderr)
    except zipfile.BadZipFile as e:
        print(f"ERROR: Invalid zip file: {e}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to parse archive: {e}", file=sys.stderr)

    # print(f"INFO: {file_name}: Skipped {skipped_logs} logs, last timestamp {last_timestamp}", file=sys.stderr)
    return log_lines, last_timestamp

def update_log_stat(log_stat, log_id, last_timestamp):
    """Update per-log_id last_timestamp and purge entries older than 2 days.

    log_stat structure:
        { 'startTime': <ISO8601 string with optional 'Z'>,
          'endTime': <ISO8601 string with optional 'Z'>,
          'logs_stat': { log_id: { 'last_timestamp': <ISO8601 string with optional 'Z'> }, ... }
        }
    """

    # Update / insert current log_id
    if log_id not in log_stat:
        log_stat[log_id] = {'last_timestamp': last_timestamp}
    else:
        log_stat[log_id]['last_timestamp'] = last_timestamp

def main():
    """Main execution function"""
    
    if not API_KEY:
        print("ERROR: SKYSQL_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Determine time range for log collection
    checkpoint = load_checkpoint()
    log_stat = checkpoint.get('logs_stat', {})
    
    # Fetch log metadata with pagination
    offset = 0
    limit = 100
    total_logs_fetched = 0
    total_lines_output = 0

    # Load polling interval from inputs.conf so this script stays in sync
    polling_interval = load_interval_from_inputs_conf(default_interval=300)
    print(f"INFO: Using polling interval {polling_interval} seconds", file=sys.stderr)

    if checkpoint:
        from_date = checkpoint.get('startTime')
        to_date = checkpoint.get('endTime')
    else:
        # First run: collect logs from 00:00:00 UTC today
        from_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        to_date = datetime.utcnow().isoformat() + 'Z'

    while True:
        # print(f"INFO: Fetching log metadata for time range {from_date} to {to_date}", file=sys.stderr)
        result = fetch_log_metadata(from_date, to_date, limit, offset)
        
        if not result:
            print(f"INFO: No result returned", file=sys.stderr)
            break
        
        logs = result.get('logs', [])
        count = result.get('count', 0)
        
        # print(f"INFO: Fetched {len(logs)} log files for time range {from_date} to {to_date}", file=sys.stderr)
        if not logs:
            print(f"INFO: No logs found for time range {from_date} to {to_date}", file=sys.stderr)
        else:
            for log in logs:
                if log.get('logType') == 'slow-query-log':
                    # TODO: Handle slow-query-log separately
                    continue
                log_id = log.get('id')
                # print(f"INFO: Fetching archive for {log_id}, logType {log.get('logType')}", file=sys.stderr)
                
                # Fetch archive for these log IDs
                archive_content = fetch_log_archive(log_id)
                
                if archive_content:
                    # Parse the archive and extract log lines
                    # For now, use the first log's logType as default for all lines in the archive
                    log_type = log.get('logType')
                    log_lines, last_timestamp = parse_log_archive(archive_content, log_type=log_type, last_timestamp=log_stat.get(log_id, {}).get('last_timestamp', 0))

                    update_log_stat(log_stat, log_id, last_timestamp)

                    print(f"INFO: Extracted {len(log_lines)} log lines from archive {log_id}, file name {log.get('name')}", file=sys.stderr)

                    # Output each log line to stdout in JSON format for Splunk
                    for log_line in log_lines:
                        event = {
                            'time': log_line.get('timestamp', to_date),
                            'source': 'skysql_logs_archive',
                            'sourcetype': 'skysql:logs:archive',
                            'event': {
                                'message': log_line.get('message'),
                                'filename': log_line.get('filename'),
                                'logType': log_type,
                                'log.level': log_line.get('log.level'),
                                'server': log.get('server'),
                                'service': log.get('service'),
                                'serverDataSourceId': log.get('serverDataSourceId')
                            }
                        }
                        print(json.dumps(event), flush=True)
                        total_lines_output += 1
                else:
                    print(f"WARNING: Failed to fetch archive for log IDs: {log_id}", file=sys.stderr)

            # Save checkpoint
            save_checkpoint(from_date, to_date, log_stat)

            total_logs_fetched = len(logs)

            # Check if there are more logs to fetch
            if total_logs_fetched >= count:
                print(f"INFO: Fetched {total_logs_fetched} log files, extracted {total_lines_output} log lines from SkySQL", file=sys.stderr)

        # print(f"INFO: sleeping for {polling_interval} seconds", file=sys.stderr)
        time.sleep(polling_interval)  # Rate limiting based on inputs.conf

        # Update start time for next run
        from_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        to_date = datetime.utcnow().isoformat() + 'Z'
    
if __name__ == '__main__':
    main()
