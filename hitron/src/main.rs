mod api;
mod discord;

use anyhow::Result;
use clap::Parser;
use std::time::Duration;
use tokio::time;
use tracing::{info, error};

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

    // On startup, send the most recent event
    match api::get_event_log(&client).await {
        Ok(events) => {
            if let Some(most_recent) = events.first() {
                info!("Sending most recent event on startup");
                if let Err(e) = notifier.send_event(most_recent).await {
                    error!("Failed to send initial event: {}", e);
                }
            } else {
                info!("No events found on startup");
            }
        }
        Err(e) => {
            error!("Failed to fetch initial event log: {}", e);
        }
    }

    // Keep track of previously seen events
    let mut previous_events: Vec<api::EventLog> = Vec::new();

    // Start polling loop
    let mut interval_timer = time::interval(Duration::from_secs(args.interval));

    loop {
        interval_timer.tick().await;

        match api::get_event_log(&client).await {
            Ok(current_events) => {
                // Find new events by comparing with previous poll
                // Events are assumed to be ordered with most recent first
                let new_events: Vec<_> = current_events
                    .iter()
                    .take_while(|event| {
                        // Check if this event wasn't in the previous list by comparing index
                        !previous_events.iter().any(|prev| prev.index == event.index)
                    })
                    .cloned()
                    .collect();

                if !new_events.is_empty() {
                    info!("Found {} new event(s)", new_events.len());
                    for event in &new_events {
                        if let Err(e) = notifier.send_event(event).await {
                            error!("Failed to send event: {}", e);
                        }
                    }
                }

                // Update previous events
                previous_events = current_events;
            }
            Err(e) => {
                error!("Failed to fetch event log: {}", e);
            }
        }
    }
}
