#!/usr/bin/env python3
"""
Hitron CODA56 Modem Information Retrieval Script
Retrieves diagnostic information from the modem's HTTP API
"""

import requests
import json
import urllib3
from typing import Optional, Dict, List, Any

# Disable SSL warnings since we're using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Modem configuration
MODEM_IP = "192.168.100.1"
BASE_URL = f"https://{MODEM_IP}/data"


def make_request(endpoint: str) -> Optional[Any]:
    """
    Make a request to the modem API endpoint

    Args:
        endpoint: The API endpoint (without /data/ prefix)

    Returns:
        Parsed JSON response or None if request fails
    """
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, verify=False, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {endpoint}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from {endpoint}: {e}")
        return None


def get_system_info() -> Optional[List[Dict]]:
    """Get system information (hardware/software version, uptime, etc.)"""
    return make_request("getSysInfo.asp")


def get_link_status() -> Optional[List[Dict]]:
    """Get LAN port link status"""
    return make_request("getLinkStatus.asp")


def get_docsis_wan() -> Optional[List[Dict]]:
    """Get DOCSIS WAN configuration"""
    return make_request("getCmDocsisWan.asp")


def get_downstream_info() -> Optional[List[Dict]]:
    """Get downstream channel information"""
    return make_request("dsinfo.asp")


def get_upstream_info() -> Optional[List[Dict]]:
    """Get upstream channel information"""
    return make_request("usinfo.asp")


def get_submenu() -> Optional[List[Dict]]:
    """Get submenu structure (shows available pages)"""
    return make_request("getSubMenu.asp")


def get_event_log() -> Optional[List[Dict]]:
    """Get DOCSIS event log (hidden diagnostic page)"""
    return make_request("status_log.asp")


def get_downstream_ofdm() -> Optional[List[Dict]]:
    """Get OFDM downstream channel information"""
    return make_request("dsofdminfo.asp")


def get_upstream_ofdm() -> Optional[List[Dict]]:
    """Get OFDM upstream channel information"""
    return make_request("usofdminfo.asp")


def get_system_model() -> Optional[Dict]:
    """Get system model information"""
    return make_request("system_model.asp")


def get_main_menu() -> Optional[List[Dict]]:
    """Get main menu structure"""
    return make_request("getMenu.asp")


def print_section(title: str, data: Any, indent: int = 0):
    """
    Print a section with formatted data

    Args:
        title: Section title
        data: Data to print
        indent: Indentation level
    """
    prefix = "  " * indent
    print(f"\n{prefix}{'=' * 60}")
    print(f"{prefix}{title}")
    print(f"{prefix}{'=' * 60}")

    if data is None:
        print(f"{prefix}[No data available]")
        return

    if isinstance(data, list):
        for i, item in enumerate(data):
            if len(data) > 1:
                print(f"{prefix}--- Item {i+1} ---")
            print_dict(item, indent + 1)
    elif isinstance(data, dict):
        print_dict(data, indent + 1)
    else:
        print(f"{prefix}{data}")


def print_dict(d: Dict, indent: int = 0):
    """Print dictionary with proper formatting"""
    prefix = "  " * indent
    for key, value in d.items():
        if isinstance(value, (dict, list)):
            print(f"{prefix}{key}:")
            print_section("", value, indent + 1)
        else:
            print(f"{prefix}{key}: {value}")


def print_channel_summary(channels: List[Dict], channel_type: str):
    """Print a summary of channel information"""
    if not channels:
        return

    print(f"\n{channel_type} Channel Summary:")
    print(f"Total Channels: {len(channels)}")

    if channel_type == "Downstream":
        # Calculate average signal strength and SNR
        avg_signal = sum(float(ch.get('signalStrength', 0)) for ch in channels) / len(channels)
        avg_snr = sum(float(ch.get('snr', 0)) for ch in channels) / len(channels)
        total_corrected = sum(int(ch.get('correcteds', 0)) for ch in channels)
        total_uncorrected = sum(int(ch.get('uncorrect', 0)) for ch in channels)

        print(f"Average Signal Strength: {avg_signal:.2f} dBmV")
        print(f"Average SNR: {avg_snr:.2f} dB")
        print(f"Total Corrected Errors: {total_corrected}")
        print(f"Total Uncorrected Errors: {total_uncorrected}")
    else:  # Upstream
        avg_power = sum(float(ch.get('signalStrength', 0)) for ch in channels) / len(channels)
        print(f"Average Transmit Power: {avg_power:.2f} dBmV")


def main():
    """Main function to retrieve and display all modem information"""
    print("=" * 60)
    print("Hitron CODA56 Modem Information")
    print("=" * 60)

    # Get and display system model
    sys_model = get_system_model()
    print_section("System Model", sys_model)

    # Get and display system information
    sys_info = get_system_info()
    print_section("System Information", sys_info)

    # Get and display LAN link status
    link_status = get_link_status()
    print_section("LAN Port Status", link_status)

    # Get and display DOCSIS WAN info
    docsis_wan = get_docsis_wan()
    print_section("DOCSIS WAN Configuration", docsis_wan)

    # Get and display downstream channels
    downstream = get_downstream_info()
    print_section("Downstream Channels (SC-QAM)", downstream)
    if downstream:
        print_channel_summary(downstream, "Downstream")

    # Get and display OFDM downstream channels
    downstream_ofdm = get_downstream_ofdm()
    print_section("Downstream Channels (OFDM)", downstream_ofdm)

    # Get and display upstream channels
    upstream = get_upstream_info()
    print_section("Upstream Channels (SC-QAM)", upstream)
    if upstream:
        print_channel_summary(upstream, "Upstream")

    # Get and display OFDM upstream channels
    upstream_ofdm = get_upstream_ofdm()
    print_section("Upstream Channels (OFDMA)", upstream_ofdm)

    # Get and display event log (HIDDEN DIAGNOSTIC PAGE!)
    event_log = get_event_log()
    print_section("DOCSIS Event Log (Hidden Page)", event_log)
    if event_log:
        print(f"\nTotal Events: {len(event_log)}")
        critical_events = [e for e in event_log if e.get('priority') == 'critical']
        warning_events = [e for e in event_log if e.get('priority') == 'warning']
        print(f"Critical Events: {len(critical_events)}")
        print(f"Warning Events: {len(warning_events)}")

    # Get and display main menu
    main_menu = get_main_menu()
    print_section("Main Menu Structure", main_menu)

    # Get and display submenu (shows available/hidden pages)
    submenu = get_submenu()
    print_section("Status Submenu Items", submenu)

    print("\n" + "=" * 60)
    print("Data retrieval complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
