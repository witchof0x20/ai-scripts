# hitron

Diagnostic tools for Hitron CODA56 cable modem monitoring.

## Overview

This package retrieves and displays diagnostic information from Hitron CODA56 cable modems via their HTTP API. It provides comprehensive visibility into modem status, signal quality, and channel information.

## Features

- System information (hardware/software version, uptime)
- LAN port link status
- DOCSIS WAN configuration
- Downstream channel information (SC-QAM and OFDM)
- Upstream channel information (SC-QAM and OFDMA)
- Signal quality metrics (power, SNR, errors)
- DOCSIS event log access (including hidden diagnostic pages)
- Channel statistics and summaries

## Configuration

The script defaults to the standard modem IP address `192.168.100.1`. Modify the `MODEM_IP` constant in `modeminfo.py` if your modem uses a different address.

## Usage

```bash
python modeminfo.py
```

The script will display comprehensive diagnostic information including:
- Average signal strength and SNR for downstream channels
- Total corrected/uncorrected errors
- Average transmit power for upstream channels
- Event log analysis (critical/warning event counts)

## Output Sections

- System Model
- System Information
- LAN Port Status
- DOCSIS WAN Configuration
- Downstream Channels (SC-QAM and OFDM)
- Upstream Channels (SC-QAM and OFDMA)
- DOCSIS Event Log (hidden diagnostic page)
- Menu Structure

## Dependencies

- `requests` - HTTP client
- `urllib3` - SSL warning suppression

## Notes

- The script disables SSL certificate verification since the modem uses a self-signed certificate
- Some endpoints are hidden diagnostic pages not accessible through the normal web interface
- Useful for troubleshooting cable internet connectivity issues
