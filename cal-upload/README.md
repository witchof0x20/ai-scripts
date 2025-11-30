# cal-upload

Upload ICS calendar events from clipboard to Nextcloud calendar.

## Overview

This script reads ICS (iCalendar) data from your clipboard and uploads the events to a specified Nextcloud calendar using CalDAV.

## Features

- Reads ICS data directly from clipboard
- Securely stores Nextcloud credentials in XDG config directory
- Uploads all events from an ICS file to a target calendar
- Validates ICS data before uploading

## Configuration

On first run, the script will prompt for:
- Nextcloud URL
- Username
- Password

Credentials are stored in `~/.config/nextcloud-cal/config.json` with permissions set to `0o600`.

## Usage

```bash
./cal_upload.py <calendar_name>
```

Where `<calendar_name>` is the name of the target calendar in Nextcloud.

## Requirements

- Python 3
- `pyperclip` - Clipboard access
- `caldav` - CalDAV client
- `icalendar` - ICS parsing

## Example

1. Copy ICS data to clipboard (from email, website, etc.)
2. Run: `./cal_upload.py "Work Calendar"`
3. Events will be uploaded to the "Work Calendar" in Nextcloud
