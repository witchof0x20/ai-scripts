mod api;
mod dedup;
mod discord;
mod monitor;

use anyhow::Result;
use clap::Parser;
use std::collections::HashSet;
use std::time::Duration;
use std::path::PathBuf;
use tokio::time;
use tokio::fs;
use tracing::{info, error, debug, warn};

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

    /// Path to state file for tracking already-seen events (optional)
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

    /// Alert if error rate (uncorrected/(corrected+uncorrected)) exceeds this threshold (0.01 = 1%)
    #[arg(long, default_value = "0.01")]
    error_rate_threshold: f64,
}

/// Load the set of already-seen events from the state file
async fn load_seen_events(state_file: &Option<PathBuf>) -> Option<HashSet<dedup::EventKey>> {
    let path = state_file.as_ref()?;

    match fs::read_to_string(path).await {
        Ok(contents) => {
            let seen = dedup::parse_state(&contents);
            match &seen {
                Some(keys) => debug!("Loaded {} seen event(s) from state file", keys.len()),
                // Covers the legacy format, which held a bare timestamp
                None => info!("State file is not a seen-event list, starting fresh"),
            }
            seen
        }
        Err(e) => {
            debug!("Could not read state file ({}), starting fresh", e);
            None
        }
    }
}

/// Save the set of already-seen events to the state file
async fn save_seen_events(state_file: &Option<PathBuf>, seen: &HashSet<dedup::EventKey>) -> Result<()> {
    if let Some(path) = state_file {
        // Create parent directory if it doesn't exist
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).await?;
        }

        fs::write(path, dedup::serialize_state(seen)).await?;
        debug!("Saved {} seen event(s)", seen.len());
    }
    Ok(())
}

/// Log a new event and forward it to Discord if it warrants a notification
async fn report_event(event: &api::EventLog, notifier: &discord::DiscordNotifier) {
    match event.parse_timestamp() {
        // The modem stamps events logged before it syncs time-of-day with
        // the Unix epoch in local time (e.g. "12/31/69 19:01:07"); they are
        // reboot-window noise, so keep them out of Discord
        Ok(ts) if dedup::is_pre_sync_timestamp(&ts) => {
            error!(
                "Ignoring pre-clock-sync event ('{}'): [{}] {} - {}",
                event.time, event.priority, event.event_type, event.event
            );
            return;
        }
        Ok(_) => {}
        Err(e) => warn!("Failed to parse timestamp for event: {}", e),
    }

    info!("Event: [{}] {} - {}", event.priority, event.event_type, event.event);

    // Only send non-Notice events to Discord webhook
    if event.priority != api::EventPriority::Notice {
        if let Err(e) = notifier.send_event(event).await {
            error!("Failed to send event: {}", e);
        }
    }
}

/// Report events not seen on the previous poll, then persist the new snapshot
async fn process_event_log(
    events: &[api::EventLog],
    seen: &mut Option<HashSet<dedup::EventKey>>,
    notifier: &discord::DiscordNotifier,
    state_file: &Option<PathBuf>,
) {
    match seen {
        Some(keys) => {
            let new_events = dedup::new_events(events, keys);
            if !new_events.is_empty() {
                info!("Found {} new event(s)", new_events.len());
                for event in new_events {
                    report_event(event, notifier).await;
                }
            }
        }
        // First run - report only the most recent event rather than
        // replaying the modem's whole rolling log
        None => match events.first() {
            Some(most_recent) => {
                info!("First run - reporting most recent event only");
                report_event(most_recent, notifier).await;
            }
            None => info!("No events found on first run"),
        },
    }

    *seen = Some(dedup::snapshot(events));
    if let Some(keys) = seen {
        if let Err(e) = save_seen_events(state_file, keys).await {
            error!("Failed to save state: {}", e);
        }
    }
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

    // Load already-seen events from state file
    let mut seen_events = load_seen_events(&args.state_file).await;

    // Initialize channel monitoring
    let thresholds = monitor::ChannelThresholds {
        downstream_snr_min: args.downstream_snr_min,
        downstream_signal_min: args.downstream_signal_min,
        downstream_signal_max: args.downstream_signal_max,
        upstream_signal_min: args.upstream_signal_min,
        upstream_signal_max: args.upstream_signal_max,
        error_rate_threshold: args.error_rate_threshold,
    };
    let mut channel_state = monitor::ChannelState::new();

    // On startup, send new events since last run
    match api::get_event_log(&client).await {
        Ok(events) => {
            process_event_log(&events, &mut seen_events, &notifier, &args.state_file).await;
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
                process_event_log(&current_events, &mut seen_events, &notifier, &args.state_file).await;
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
