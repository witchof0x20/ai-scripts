#!/usr/bin/env python3
import tomllib
import requests
import argparse
import os
from datetime import datetime

def load_tasks(filepath: str):
    """Load tasks from TOML file."""
    try:
        with open(filepath, 'rb') as f:
            return tomllib.load(f)
    except Exception as e:
        raise Exception(f"Failed to load TOML file: {e}")

def send_discord_message(webhook_url: str, tasks):
    """Send formatted task list to Discord webhook."""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    embed = {
        "title": f"📅 Daily Tasks for {current_date}",
        "color": 0x00ff00,
        "fields": [
            {
                "name": "📝 Tasks",
                "value": "\n".join([f"• {task}" for task in tasks]),
            }
        ],
        "footer": {
            "text": "Stay productive! ✨"
        }
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to send Discord message: {e}")

def main():
    parser = argparse.ArgumentParser(description='Send daily tasks to Discord webhook')
    parser.add_argument('--config', '-c', 
                      type=str, 
                      default='tasks.toml',
                      help='Path to TOML config file (default: tasks.toml)')
    
    args = parser.parse_args()
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL environment variable not set")
        return
    
    try:
        config = load_tasks(args.config)
        tasks = config.get('tasks', [])
        
        if not tasks:
            print("No tasks found in TOML file")
            return
            
        send_discord_message(webhook_url, tasks)
        print("Successfully sent task reminder to Discord")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
