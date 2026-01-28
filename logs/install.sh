#!/bin/bash
#
# SkySQL Logs Integration - Installation Script
# Automates the installation of SkySQL Logs integration for Splunk Universal Forwarder
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SPLUNK_HOME="${SPLUNK_HOME:-/opt/splunkforwarder}"
APP_NAME="splunk-skysql-integration"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${GREEN}SkySQL Logs Integration - Installation Script${NC}"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

# Check if Splunk Universal Forwarder is installed
if [ ! -d "$SPLUNK_HOME" ]; then
    echo -e "${RED}Error: Splunk Universal Forwarder not found at $SPLUNK_HOME${NC}"
    echo "Please install Splunk Universal Forwarder first or set SPLUNK_HOME environment variable"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found Splunk Universal Forwarder at $SPLUNK_HOME"

# Check if Python 3 is available
if ! $SPLUNK_HOME/bin/splunk cmd python3 --version &> /dev/null; then
    echo -e "${RED}Error: Python 3 not available in Splunk${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 is available"

# Prompt for API key
echo ""
echo -e "${YELLOW}Please enter your SkySQL API Key:${NC}"
read API_KEY
echo ""

if [ -z "$API_KEY" ]; then
    echo -e "${RED}Error: API key cannot be empty${NC}"
    exit 1
fi

# Prompt for API URL (optional)
echo -e "${YELLOW}Enter SkySQL API URL [https://api.skysql.com]:${NC}"
read API_URL
API_URL="${API_URL:-https://api.skysql.com}"

# Prompt for polling interval
echo -e "${YELLOW}Enter polling interval in seconds [300]:${NC}"
read INTERVAL
INTERVAL="${INTERVAL:-300}"

# Copy app to Splunk
echo ""
echo "Installing app to $SPLUNK_HOME/etc/apps/$APP_NAME..."

# Create app directory if it doesn't exist
mkdir -p "$SPLUNK_HOME/etc/apps/$APP_NAME"

# Copy files
cp -r "$SCRIPT_DIR/default" "$SPLUNK_HOME/etc/apps/$APP_NAME/"
cp -r "$SCRIPT_DIR/scripts" "$SPLUNK_HOME/bin/"
mkdir -p "$SPLUNK_HOME/etc/apps/$APP_NAME/local"

echo -e "${GREEN}✓${NC} App files copied"

# Update wrapper script with API key
# WRAPPER_SCRIPT="$SPLUNK_HOME/etc/apps/$APP_NAME/scripts/skysql_logs_wrapper.sh"
WRAPPER_SCRIPT="$SPLUNK_HOME/bin/scripts/skysql_logs_wrapper.sh"
sed -i.bak "s|your-api-key-here|$API_KEY|g" "$WRAPPER_SCRIPT"
sed -i.bak "s|https://api.skysql.com|$API_URL|g" "$WRAPPER_SCRIPT"
rm -f "$WRAPPER_SCRIPT.bak"

echo -e "${GREEN}✓${NC} API key configured"

# Update polling interval if different from default
if [ "$INTERVAL" != "300" ]; then
    INPUTS_CONF="$SPLUNK_HOME/etc/apps/$APP_NAME/default/inputs.conf"
    sed -i.bak "s|interval = 300|interval = $INTERVAL|g" "$INPUTS_CONF"
    rm -f "$INPUTS_CONF.bak"
    echo -e "${GREEN}✓${NC} Polling interval set to $INTERVAL seconds"
fi

# Set permissions
chmod +x "$SPLUNK_HOME/bin/scripts/"*.sh
chmod +x "$SPLUNK_HOME/bin/scripts/"*.py

# Get splunk user (usually 'splunk')
SPLUNK_USER=$(stat -c '%u' "$SPLUNK_HOME/bin/splunk" 2>/dev/null || stat -c '%U' "$SPLUNK_HOME/bin/splunk" 2>/dev/null || echo "splunk")
chown -R "$SPLUNK_USER:$SPLUNK_USER" "$SPLUNK_HOME/etc/apps/$APP_NAME"

echo -e "${GREEN}✓${NC} Permissions set"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if $SPLUNK_HOME/bin/splunk cmd python3 -m pip install requests &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python dependencies installed"
else
    echo -e "${YELLOW}Warning: Failed to install Python dependencies${NC}"
    echo "You may need to install 'requests' manually:"
    echo "  $SPLUNK_HOME/bin/splunk cmd python3 -m pip install requests"
fi

# Test the script
echo ""
echo "Testing the integration..."
if sudo -u "$SPLUNK_USER" "$WRAPPER_SCRIPT" 2>&1 | grep -q "INFO:"; then
    echo -e "${GREEN}✓${NC} Script test successful"
else
    echo -e "${YELLOW}Warning: Script test returned warnings (this may be normal on first run)${NC}"
fi

# Prompt to restart Splunk
echo ""
echo -e "${YELLOW}Installation complete!${NC}"
echo ""
echo "To activate the integration, restart Splunk Universal Forwarder:"
echo "  $SPLUNK_HOME/bin/splunk restart"
echo ""
echo "To verify logs are being collected, check:"
echo "  tail -f $SPLUNK_HOME/var/log/splunk/splunkd.log | grep skysql"
echo ""
echo "In Splunk, search for:"
echo "  index=skysql_logs sourcetype=skysql:logs"
echo ""

# Ask if user wants to restart now
read -p "Restart Splunk Universal Forwarder now? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restarting Splunk Universal Forwarder..."
    $SPLUNK_HOME/bin/splunk restart
    echo -e "${GREEN}✓${NC} Splunk restarted"
else
    echo "Remember to restart Splunk manually to activate the integration"
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
