use anyhow::Result;
use reqwest::Client;
use serde::{Deserialize, Deserializer};
use std::fmt;
use tracing::debug;

const BASE_URL: &str = "https://192.168.100.1/data";

/// Create a reqwest client that accepts self-signed certificates
pub fn create_client() -> Result<Client> {
    let client = Client::builder()
        .danger_accept_invalid_certs(true)
        .timeout(std::time::Duration::from_secs(5))
        .build()?;
    Ok(client)
}

/// Custom deserializer for converting string to f64
fn deserialize_string_to_f64<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: Deserializer<'de>,
{
    let s: String = Deserialize::deserialize(deserializer)?;
    s.parse().map_err(serde::de::Error::custom)
}

/// Custom deserializer for converting string to i64
fn deserialize_string_to_i64<'de, D>(deserializer: D) -> Result<i64, D::Error>
where
    D: Deserializer<'de>,
{
    let s: String = Deserialize::deserialize(deserializer)?;
    s.parse().map_err(serde::de::Error::custom)
}

/// Custom deserializer for converting string to u32
fn deserialize_string_to_u32<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: Deserializer<'de>,
{
    let s: String = Deserialize::deserialize(deserializer)?;
    s.parse().map_err(serde::de::Error::custom)
}

// Endpoint structs

#[derive(Debug, Deserialize, Clone)]
pub struct SystemModel {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SystemInfo {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct LinkStatus {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DocsisWan {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DownstreamChannel {
    #[serde(rename = "portId", deserialize_with = "deserialize_string_to_u32")]
    pub port_id: u32,
    #[serde(deserialize_with = "deserialize_string_to_f64")]
    pub frequency: f64,
    pub modulation: String,
    #[serde(rename = "signalStrength", deserialize_with = "deserialize_string_to_f64")]
    pub signal_strength: f64,
    #[serde(deserialize_with = "deserialize_string_to_f64")]
    pub snr: f64,
    #[serde(deserialize_with = "deserialize_string_to_i64")]
    pub correcteds: i64,
    #[serde(deserialize_with = "deserialize_string_to_i64")]
    pub uncorrect: i64,
    #[serde(rename = "channelId", deserialize_with = "deserialize_string_to_u32")]
    pub channel_id: u32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DownstreamOfdm {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct UpstreamChannel {
    #[serde(rename = "portId", deserialize_with = "deserialize_string_to_u32")]
    pub port_id: u32,
    #[serde(deserialize_with = "deserialize_string_to_f64")]
    pub frequency: f64,
    #[serde(rename = "bandwidth")]
    pub bandwidth: String,
    #[serde(rename = "modtype")]
    pub modulation_type: String,
    #[serde(rename = "signalStrength", deserialize_with = "deserialize_string_to_f64")]
    pub signal_strength: f64,
    #[serde(rename = "channelId", deserialize_with = "deserialize_string_to_u32")]
    pub channel_id: u32,
}

#[derive(Debug, Deserialize, Clone)]
pub struct UpstreamOfdm {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum EventPriority {
    Critical,
    Warning,
    Notice,
    #[serde(other)]
    Other,
}

impl fmt::Display for EventPriority {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EventPriority::Critical => write!(f, "critical"),
            EventPriority::Warning => write!(f, "warning"),
            EventPriority::Notice => write!(f, "notice"),
            EventPriority::Other => write!(f, "other"),
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct EventLog {
    pub index: u32,
    pub time: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub priority: EventPriority,
    pub event: String,
}

impl EventLog {
    /// Parse the timestamp from the event
    /// Format: "MM/DD/YY HH:MM:SS"
    pub fn parse_timestamp(&self) -> Result<chrono::NaiveDateTime> {
        chrono::NaiveDateTime::parse_from_str(&self.time, "%m/%d/%y %H:%M:%S")
            .map_err(|e| anyhow::anyhow!("Failed to parse timestamp '{}': {}", self.time, e))
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct Menu {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

#[derive(Debug, Deserialize, Clone)]
pub struct SubMenu {
    #[serde(flatten)]
    pub fields: serde_json::Value,
}

// API functions

pub async fn get_system_model(client: &Client) -> Result<SystemModel> {
    let url = format!("{}/system_model.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_system_info(client: &Client) -> Result<Vec<SystemInfo>> {
    let url = format!("{}/getSysInfo.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_link_status(client: &Client) -> Result<Vec<LinkStatus>> {
    let url = format!("{}/getLinkStatus.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_docsis_wan(client: &Client) -> Result<Vec<DocsisWan>> {
    let url = format!("{}/getCmDocsisWan.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_downstream_info(client: &Client) -> Result<Vec<DownstreamChannel>> {
    let url = format!("{}/dsinfo.asp", BASE_URL);
    debug!("Fetching downstream info from: {}", url);

    let response = client.get(&url).send().await?;
    let bytes = response.bytes().await?;
    let text = String::from_utf8_lossy(&bytes);
    let channels: Vec<DownstreamChannel> = serde_json::from_str(&text)?;

    debug!("Parsed {} downstream channels", channels.len());
    Ok(channels)
}

pub async fn get_downstream_ofdm(client: &Client) -> Result<Vec<DownstreamOfdm>> {
    let url = format!("{}/dsofdminfo.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_upstream_info(client: &Client) -> Result<Vec<UpstreamChannel>> {
    let url = format!("{}/usinfo.asp", BASE_URL);
    debug!("Fetching upstream info from: {}", url);

    let response = client.get(&url).send().await?;
    let bytes = response.bytes().await?;
    let text = String::from_utf8_lossy(&bytes);
    let channels: Vec<UpstreamChannel> = serde_json::from_str(&text)?;

    debug!("Parsed {} upstream channels", channels.len());
    Ok(channels)
}

pub async fn get_upstream_ofdm(client: &Client) -> Result<Vec<UpstreamOfdm>> {
    let url = format!("{}/usofdminfo.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_event_log(client: &Client) -> Result<Vec<EventLog>> {
    let url = format!("{}/status_log.asp", BASE_URL);
    debug!("Fetching event log from: {}", url);

    let response = client.get(&url).send().await?;
    debug!("Response status: {}", response.status());

    let bytes = response.bytes().await?;
    debug!("Received {} bytes", bytes.len());

    let text = String::from_utf8_lossy(&bytes);
    let events: Vec<EventLog> = serde_json::from_str(&text)?;

    debug!("Parsed {} events", events.len());
    Ok(events)
}

pub async fn get_main_menu(client: &Client) -> Result<Vec<Menu>> {
    let url = format!("{}/getMenu.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}

pub async fn get_submenu(client: &Client) -> Result<Vec<SubMenu>> {
    let url = format!("{}/getSubMenu.asp", BASE_URL);
    let response = client.get(&url).send().await?;
    Ok(response.json().await?)
}
