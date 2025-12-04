use anyhow::Result;
use serenity::http::Http;
use serenity::model::webhook::Webhook;
use serenity::builder::ExecuteWebhook;
use serenity::all::CreateEmbed;
use crate::api::EventLog;
use crate::monitor::ChannelAnomaly;

pub struct DiscordNotifier {
    webhook: Webhook,
    http: Http,
    role_id: Option<u64>,
}

impl DiscordNotifier {
    /// Create a new Discord notifier from a webhook URL
    pub async fn new(webhook_url: &str, role_id: Option<u64>) -> Result<Self> {
        let http = Http::new("");
        let webhook = Webhook::from_url(&http, webhook_url).await?;
        Ok(Self { webhook, http, role_id })
    }

    /// Send an event log entry to Discord
    pub async fn send_event(&self, event: &EventLog) -> Result<()> {
        // Create an embed with color based on priority
        let color = match event.priority {
            crate::api::EventPriority::Critical => 0xFF0000, // Red
            crate::api::EventPriority::Warning => 0xFFA500,  // Orange
            crate::api::EventPriority::Notice => 0x0099FF,   // Blue
            crate::api::EventPriority::Other => 0x808080,    // Gray
        };

        let description = format!(
            "**Time:** {}\n**Type:** {}\n**Event:** {}",
            event.time, event.event_type, event.event
        );

        let embed = CreateEmbed::new()
            .title(format!("Modem Event: {}", event.priority))
            .color(color)
            .description(description)
            .timestamp(serenity::model::Timestamp::now());

        let mut builder = ExecuteWebhook::new().embed(embed);

        // Add role mention if specified, but not for Notice level events
        if let Some(role_id) = self.role_id {
            if event.priority != crate::api::EventPriority::Notice {
                builder = builder.content(format!("<@&{}>", role_id));
            }
        }

        self.webhook.execute(&self.http, false, builder).await?;

        Ok(())
    }

    /// Send a channel anomaly alert to Discord
    pub async fn send_channel_alert(&self, anomaly: &ChannelAnomaly) -> Result<()> {
        // Determine color and title based on anomaly type
        let (color, title) = match anomaly {
            ChannelAnomaly::DownstreamLowSNR { .. } => (0xFFA500, "⚠️ Low SNR Detected"),
            ChannelAnomaly::DownstreamSignalOutOfRange { .. } => (0xFFA500, "⚠️ Downstream Signal Out of Range"),
            ChannelAnomaly::UpstreamSignalOutOfRange { .. } => (0xFFA500, "⚠️ Upstream Signal Out of Range"),
            ChannelAnomaly::HighErrorRate { triggered_channels, .. } => {
                let title = if triggered_channels.len() == 1 {
                    "🔴 High Error Rate Detected"
                } else {
                    "🔴 High Error Rates Detected"
                };
                (0xFF0000, title)
            },
        };

        let embed = CreateEmbed::new()
            .title(title)
            .color(color)
            .description(anomaly.to_string())
            .timestamp(serenity::model::Timestamp::now());

        let mut builder = ExecuteWebhook::new().embed(embed);

        // Add role mention if specified
        if let Some(role_id) = self.role_id {
            builder = builder.content(format!("<@&{}>", role_id));
        }

        self.webhook.execute(&self.http, false, builder).await?;

        Ok(())
    }
}
