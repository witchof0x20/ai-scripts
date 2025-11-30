mod api;
mod discord;

use anyhow::Result;
use clap::Parser;
use std::time::Duration;
use std::path::PathBuf;
use tokio::time;
use tokio::fs;
use tracing::{info, error, debug};

#[derive(Parser, Debug)]
#[command(author, version, about = "Monitor Hitron modem event logs and send notifications to Discord", long_about = None)]
struct Args {
    /// Discord webhook URL (can also be set via DISCORD_WEBHOOK env var)
    #[arg(short, long, env = "DISCORD_WEBHOOK")]
    webhook: String,

    /// Poll interval in seconds
    #[arg(short, long, default_value = "60")]
    interval: u64,

    /// Discord role ID to ping (e.g., 123456789012345678)
    #[arg(short, long)]
    role: Option<u64>,

    /// Path to state file for tracking last seen event (optional)
    #[arg(short, long)]
    state_file: Option<PathBuf>,
}

/// Load the last seen event index from the state file
async fn load_last_seen_index(state_file: &Option<PathBuf>) -> Option<u32> {
    let path = state_file.as_ref()?;

    match fs::read_to_string(path).await {
        Ok(contents) => {
            match contents.trim().parse::<u32>() {
                Ok(index) => {
                    debug!("Loaded last seen index: {}", index);
                    Some(index)
                }
                Err(e) => {
                    error!("Failed to parse state file: {}", e);
                    None
                }
            }
        }
        Err(e) => {
            debug!("Could not read state file ({}), starting fresh", e);
            None
        }
    }
}

/// Save the last seen event index to the state file
async fn save_last_seen_index(state_file: &Option<PathBuf>, index: u32) -> Result<()> {
    if let Some(path) = state_file {
        // Create parent directory if it doesn't exist
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).await?;
        }

        fs::write(path, index.to_string()).await?;
        debug!("Saved last seen index: {}", index);
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    let args = Args::parse();

    // Create API client and Discord notifier
    let client = api::create_client()?;
    let notifier = discord::DiscordNotifier::new(&args.webhook, args.role).await?;

    info!("Hitron Modem Monitor started");
    info!("Polling interval: {} seconds", args.interval);
    if args.state_file.is_some() {
        info!("State persistence enabled");
    }

    // Load last seen event index from state file
    let mut last_seen_index = load_last_seen_index(&args.state_file).await;

    // On startup, send new events since last run
    match api::get_event_log(&client).await {
        Ok(events) => {
            if let Some(last_index) = last_seen_index {
                // Find events newer than last seen
                let new_events: Vec<_> = events.iter()
                    .filter(|event| event.index > last_index)
                    .collect();

                if !new_events.is_empty() {
                    info!("Found {} new event(s) since last run", new_events.len());
                    for event in &new_events {
                        if let Err(e) = notifier.send_event(event).await {
                            error!("Failed to send event: {}", e);
                        }
                    }
                } else {
                    info!("No new events since last run");
                }
            } else {
                // First run - just send the most recent event
                if let Some(most_recent) = events.first() {
                    info!("First run - sending most recent event");
                    if let Err(e) = notifier.send_event(most_recent).await {
                        error!("Failed to send initial event: {}", e);
                    }
                } else {
                    info!("No events found on startup");
                }
            }

            // Update last seen index
            if let Some(most_recent) = events.first() {
                last_seen_index = Some(most_recent.index);
                if let Err(e) = save_last_seen_index(&args.state_file, most_recent.index).await {
                    error!("Failed to save state: {}", e);
                }
            }
        }
        Err(e) => {
            error!("Failed to fetch initial event log: {}", e);
        }
    }

    // Start polling loop
    let mut interval_timer = time::interval(Duration::from_secs(args.interval));

    loop {
        interval_timer.tick().await;

        match api::get_event_log(&client).await {
            Ok(current_events) => {
                // Find new events
                let new_events: Vec<_> = if let Some(last_index) = last_seen_index {
                    // Filter events newer than last seen
                    current_events.iter()
                        .filter(|event| event.index > last_index)
                        .collect()
                } else {
                    // No state - send all events
                    current_events.iter().collect()
                };

                if !new_events.is_empty() {
                    info!("Found {} new event(s)", new_events.len());
                    for event in &new_events {
                        if let Err(e) = notifier.send_event(event).await {
                            error!("Failed to send event: {}", e);
                        }
                    }
                }

                // Update last seen index and save state
                if let Some(most_recent) = current_events.first() {
                    last_seen_index = Some(most_recent.index);
                    if let Err(e) = save_last_seen_index(&args.state_file, most_recent.index).await {
                        error!("Failed to save state: {}", e);
                    }
                }
            }
            Err(e) => {
                error!("Failed to fetch event log: {}", e);
            }
        }
    }
}
