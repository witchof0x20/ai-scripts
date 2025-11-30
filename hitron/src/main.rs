mod api;
mod discord;
mod monitor;

use anyhow::Result;
use clap::Parser;
use std::time::Duration;
use std::path::PathBuf;
use tokio::time;
use tokio::fs;
use tracing::{info, error, debug, warn};
use chrono::NaiveDateTime;

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

    /// Minimum acceptable downstream SNR in dB
    #[arg(long, default_value = "33.0")]
    downstream_snr_min: f64,

    /// Minimum acceptable downstream signal strength in dBmV
    #[arg(long, default_value = "-9.0")]
    downstream_signal_min: f64,

    /// Maximum acceptable downstream signal strength in dBmV
    #[arg(long, default_value = "15.0")]
    downstream_signal_max: f64,

    /// Minimum acceptable upstream signal strength in dBmV
    #[arg(long, default_value = "37.0")]
    upstream_signal_min: f64,

    /// Maximum acceptable upstream signal strength in dBmV
    #[arg(long, default_value = "53.0")]
    upstream_signal_max: f64,

    /// Alert if uncorrectable errors increase by this amount between polls
    #[arg(long, default_value = "100")]
    uncorrectable_error_increase: i64,
}

/// Load the last seen event timestamp from the state file
async fn load_last_seen_timestamp(state_file: &Option<PathBuf>) -> Option<NaiveDateTime> {
    let path = state_file.as_ref()?;

    match fs::read_to_string(path).await {
        Ok(contents) => {
            match NaiveDateTime::parse_from_str(contents.trim(), "%m/%d/%y %H:%M:%S") {
                Ok(timestamp) => {
                    debug!("Loaded last seen timestamp: {}", timestamp);
                    Some(timestamp)
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

/// Save the last seen event timestamp to the state file
async fn save_last_seen_timestamp(state_file: &Option<PathBuf>, timestamp: &str) -> Result<()> {
    if let Some(path) = state_file {
        // Create parent directory if it doesn't exist
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).await?;
        }

        fs::write(path, timestamp).await?;
        debug!("Saved last seen timestamp: {}", timestamp);
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

    // Load last seen event timestamp from state file
    let mut last_seen_timestamp = load_last_seen_timestamp(&args.state_file).await;

    // Initialize channel monitoring
    let thresholds = monitor::ChannelThresholds {
        downstream_snr_min: args.downstream_snr_min,
        downstream_signal_min: args.downstream_signal_min,
        downstream_signal_max: args.downstream_signal_max,
        upstream_signal_min: args.upstream_signal_min,
        upstream_signal_max: args.upstream_signal_max,
        uncorrectable_error_increase: args.uncorrectable_error_increase,
    };
    let mut channel_state = monitor::ChannelState::new();

    // On startup, send new events since last run
    match api::get_event_log(&client).await {
        Ok(events) => {
            if let Some(last_ts) = last_seen_timestamp {
                // Find events newer than last seen
                let new_events: Vec<_> = events.iter()
                    .filter(|event| {
                        match event.parse_timestamp() {
                            Ok(ts) => ts > last_ts,
                            Err(e) => {
                                warn!("Failed to parse timestamp for event: {}", e);
                                false
                            }
                        }
                    })
                    .collect();

                if !new_events.is_empty() {
                    info!("Found {} new event(s) since last run", new_events.len());
                    for event in &new_events {
                        info!("Event: [{}] {} - {}", event.priority, event.event_type, event.event);

                        // Only send non-Notice events to Discord webhook
                        if event.priority != api::EventPriority::Notice {
                            if let Err(e) = notifier.send_event(event).await {
                                error!("Failed to send event: {}", e);
                            }
                        }
                    }
                } else {
                    info!("No new events since last run");
                }
            } else {
                // First run - just send the most recent event
                if let Some(most_recent) = events.first() {
                    info!("First run - most recent event: [{}] {} - {}",
                          most_recent.priority, most_recent.event_type, most_recent.event);

                    // Only send non-Notice events to Discord webhook
                    if most_recent.priority != api::EventPriority::Notice {
                        if let Err(e) = notifier.send_event(most_recent).await {
                            error!("Failed to send initial event: {}", e);
                        }
                    }
                } else {
                    info!("No events found on startup");
                }
            }

            // Update last seen timestamp
            if let Some(most_recent) = events.first() {
                if let Ok(ts) = most_recent.parse_timestamp() {
                    last_seen_timestamp = Some(ts);
                    if let Err(e) = save_last_seen_timestamp(&args.state_file, &most_recent.time).await {
                        error!("Failed to save state: {}", e);
                    }
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
                let new_events: Vec<_> = if let Some(last_ts) = last_seen_timestamp {
                    // Filter events newer than last seen
                    current_events.iter()
                        .filter(|event| {
                            match event.parse_timestamp() {
                                Ok(ts) => ts > last_ts,
                                Err(e) => {
                                    warn!("Failed to parse timestamp for event: {}", e);
                                    false
                                }
                            }
                        })
                        .collect()
                } else {
                    // No state - send all events
                    current_events.iter().collect()
                };

                if !new_events.is_empty() {
                    info!("Found {} new event(s)", new_events.len());
                    for event in &new_events {
                        info!("Event: [{}] {} - {}", event.priority, event.event_type, event.event);

                        // Only send non-Notice events to Discord webhook
                        if event.priority != api::EventPriority::Notice {
                            if let Err(e) = notifier.send_event(event).await {
                                error!("Failed to send event: {}", e);
                            }
                        }
                    }
                }

                // Update last seen timestamp and save state
                if let Some(most_recent) = current_events.first() {
                    if let Ok(ts) = most_recent.parse_timestamp() {
                        last_seen_timestamp = Some(ts);
                        if let Err(e) = save_last_seen_timestamp(&args.state_file, &most_recent.time).await {
                            error!("Failed to save state: {}", e);
                        }
                    }
                }
            }
            Err(e) => {
                error!("Failed to fetch event log: {}", e);
            }
        }

        // Check channel status for anomalies
        let mut anomalies = Vec::new();

        // Check downstream channels
        match api::get_downstream_info(&client).await {
            Ok(channels) => {
                let downstream_anomalies = monitor::check_downstream_channels(&channels, &mut channel_state, &thresholds);
                anomalies.extend(downstream_anomalies);
            }
            Err(e) => {
                error!("Failed to fetch downstream channel info: {}", e);
            }
        }

        // Check upstream channels
        match api::get_upstream_info(&client).await {
            Ok(channels) => {
                let upstream_anomalies = monitor::check_upstream_channels(&channels, &mut channel_state, &thresholds);
                anomalies.extend(upstream_anomalies);
            }
            Err(e) => {
                error!("Failed to fetch upstream channel info: {}", e);
            }
        }

        // Send Discord notifications for anomalies
        if !anomalies.is_empty() {
            info!("Detected {} channel anomal{}", anomalies.len(), if anomalies.len() == 1 { "y" } else { "ies" });
            for anomaly in &anomalies {
                if let Err(e) = notifier.send_channel_alert(anomaly).await {
                    error!("Failed to send channel alert: {}", e);
                }
            }
        }
    }
}
