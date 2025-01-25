#!/usr/bin/env python3
import sys
import pyperclip
import caldav
from icalendar import Calendar
import os
import json
from pathlib import Path

def get_config_path():
    """Get XDG config path for credentials"""
    xdg_config = os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))
    return Path(xdg_config) / 'nextcloud-cal' / 'config.json'

def get_credentials():
    """Get Nextcloud credentials from config file"""
    config_path = get_config_path()
    
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            'url': input('Nextcloud URL: '),
            'username': input('Username: '),
            'password': input('Password: ')
        }
        config_path.write_text(json.dumps(config, indent=2))
        os.chmod(config_path, 0o600)
    else:
        config = json.loads(config_path.read_text())
    
    return config['url'], config['username'], config['password']

def parse_ics_data(ics_data):
    """Parse ICS data from string"""
    try:
        calendar = Calendar.from_ical(ics_data)
        return calendar
    except ValueError as e:
        print(f"Error parsing ICS data: {e}")
        sys.exit(1)

def connect_caldav(url, username, password):
    """Establish connection to CalDAV server"""
    try:
        base_url = url.rstrip('/')
        if not base_url.endswith('remote.php/dav'):
            base_url += '/remote.php/dav'
        
        client = caldav.DAVClient(
            url=base_url,
            username=username,
            password=password,
            ssl_verify_cert=False
        )
        principal = client.principal()
        return principal
    except caldav.lib.error.AuthorizationError:
        print("Authentication failed. Check your credentials")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to CalDAV server: {e}")
        sys.exit(1)

def find_calendar(principal, calendar_name):
    """Find calendar by name"""
    calendars = principal.calendars()
    for calendar in calendars:
        if calendar.name == calendar_name:
            return calendar
    print(f"Calendar '{calendar_name}' not found")
    sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <calendar_name>")
        sys.exit(1)

    calendar_name = sys.argv[1]
    
    # Get ICS data from clipboard
    ics_data = pyperclip.paste()
    if not ics_data.startswith('BEGIN:VCALENDAR'):
        print("No valid ICS data found in clipboard")
        sys.exit(1)

    # Parse ICS data
    calendar = parse_ics_data(ics_data)
    
    # Get credentials and connect
    url, username, password = get_credentials()
    principal = connect_caldav(url, username, password)
    
    # Find target calendar
    target_calendar = find_calendar(principal, calendar_name)
    
    # Upload each event
    for component in calendar.walk('VEVENT'):
        try:
            target_calendar.save_event(component.to_ical())
            print(f"Successfully uploaded event: {component.get('summary')}")
        except Exception as e:
            print(f"Failed to upload event: {e}")

if __name__ == "__main__":
    main()
