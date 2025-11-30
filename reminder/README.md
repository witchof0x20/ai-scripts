# reminder

Send daily task reminders to Discord via webhook.

## Overview

This script reads a list of tasks from a JSON file and sends them as a formatted embed message to a Discord channel using a webhook URL.

## Features

- Reads tasks from configurable JSON file
- Sends formatted embed messages with current date
- Environment-based webhook configuration for security
- Clean, organized task list presentation

## Configuration

### Discord Webhook

Set the webhook URL as an environment variable:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

### Tasks File

Create a `tasks.json` file (or specify a different path):

```json
{
  "tasks": [
    "Review daily emails",
    "Check project status",
    "Update documentation",
    "Team standup at 10 AM"
  ]
}
```

## Usage

```bash
./reminder.py
```

Or with a custom config file:

```bash
./reminder.py --config /path/to/custom-tasks.json
```

## Command-Line Options

- `--config`, `-c` - Path to JSON config file (default: `tasks.json`)

## Example Output

The script sends a Discord embed with:
- Title: "Daily Tasks for [Current Date]"
- Bulleted list of all tasks
- Footer message
- Green color theme

## Dependencies

- `requests` - HTTP client for webhook calls

## Use Case

Automate daily task reminders by running this script via cron or systemd timer to send recurring task lists to Discord channels.
