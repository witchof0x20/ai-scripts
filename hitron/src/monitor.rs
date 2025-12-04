use crate::api::{DownstreamChannel, UpstreamChannel};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct ChannelThresholds {
    pub downstream_snr_min: f64,
    pub downstream_signal_min: f64,
    pub downstream_signal_max: f64,
    pub upstream_signal_min: f64,
    pub upstream_signal_max: f64,
    pub error_rate_threshold: f64,
}

impl Default for ChannelThresholds {
    fn default() -> Self {
        Self {
            // DOCSIS 3.0/3.1 recommendations (adjusted for your modem)
            downstream_snr_min: 33.0,           // Minimum 33 dB for good signal
            downstream_signal_min: -9.0,        // Adjusted based on your modem
            downstream_signal_max: 15.0,        // Adjusted based on your modem
            upstream_signal_min: 37.0,          // Adjusted based on your modem
            upstream_signal_max: 53.0,          // Adjusted based on your modem
            error_rate_threshold: 0.01,         // Alert if uncorrectable/(corrected+uncorrectable) > 1%
        }
    }
}

#[derive(Debug, Clone)]
pub struct ChannelState {
    pub previous_downstream: HashMap<u32, DownstreamChannel>,
    pub previous_upstream: HashMap<u32, UpstreamChannel>,
}

impl ChannelState {
    pub fn new() -> Self {
        Self {
            previous_downstream: HashMap::new(),
            previous_upstream: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ChannelErrorStats {
    pub channel_id: u32,
    pub uncorrected_delta: i64,
    pub corrected_delta: i64,
    pub error_rate: f64,
}

#[derive(Debug, Clone)]
pub enum ChannelAnomaly {
    DownstreamLowSNR {
        channel_id: u32,
        snr: f64,
        threshold: f64,
    },
    DownstreamSignalOutOfRange {
        channel_id: u32,
        signal: f64,
        min: f64,
        max: f64,
    },
    UpstreamSignalOutOfRange {
        channel_id: u32,
        signal: f64,
        min: f64,
        max: f64,
    },
    HighErrorRate {
        threshold: f64,
        triggered_channels: Vec<ChannelErrorStats>,
    },
}

impl std::fmt::Display for ChannelAnomaly {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ChannelAnomaly::DownstreamLowSNR { channel_id, snr, threshold } => {
                write!(f, "Channel {} has low SNR: {:.1} dB (threshold: {:.1} dB)", channel_id, snr, threshold)
            }
            ChannelAnomaly::DownstreamSignalOutOfRange { channel_id, signal, min, max } => {
                write!(f, "Channel {} signal out of range: {:.1} dBmV (expected: {:.1} to {:.1} dBmV)", channel_id, signal, min, max)
            }
            ChannelAnomaly::UpstreamSignalOutOfRange { channel_id, signal, min, max } => {
                write!(f, "Upstream channel {} signal out of range: {:.1} dBmV (expected: {:.1} to {:.1} dBmV)", channel_id, signal, min, max)
            }
            ChannelAnomaly::HighErrorRate { threshold, triggered_channels } => {
                write!(f, "High error rate detected on {} channel(s) (threshold: {:.2}%)\n\n",
                    triggered_channels.len(), threshold * 100.0)?;

                for stats in triggered_channels {
                    write!(f, "• Channel {}: {:.2}% error rate (uncorrected: +{}, corrected: +{})\n",
                        stats.channel_id, stats.error_rate * 100.0, stats.uncorrected_delta, stats.corrected_delta)?;
                }

                Ok(())
            }
        }
    }
}

pub fn check_downstream_channels(
    channels: &[DownstreamChannel],
    state: &mut ChannelState,
    thresholds: &ChannelThresholds,
) -> Vec<ChannelAnomaly> {
    let mut anomalies = Vec::new();

    // Collect error stats for channels that exceed the threshold
    let mut triggered_channels = Vec::new();

    for channel in channels {
        // Check SNR
        if channel.snr < thresholds.downstream_snr_min {
            anomalies.push(ChannelAnomaly::DownstreamLowSNR {
                channel_id: channel.channel_id,
                snr: channel.snr,
                threshold: thresholds.downstream_snr_min,
            });
        }

        // Check signal strength
        if channel.signal_strength < thresholds.downstream_signal_min
            || channel.signal_strength > thresholds.downstream_signal_max
        {
            anomalies.push(ChannelAnomaly::DownstreamSignalOutOfRange {
                channel_id: channel.channel_id,
                signal: channel.signal_strength,
                min: thresholds.downstream_signal_min,
                max: thresholds.downstream_signal_max,
            });
        }

        // Check for high error rates
        if let Some(prev) = state.previous_downstream.get(&channel.channel_id) {
            let uncorrected_delta = channel.uncorrect - prev.uncorrect;
            let corrected_delta = channel.correcteds - prev.correcteds;

            // Only check if there were new errors in this interval
            if uncorrected_delta > 0 || corrected_delta > 0 {
                let total_errors = uncorrected_delta + corrected_delta;
                let error_rate = uncorrected_delta as f64 / total_errors as f64;

                if error_rate > thresholds.error_rate_threshold {
                    triggered_channels.push(ChannelErrorStats {
                        channel_id: channel.channel_id,
                        uncorrected_delta,
                        corrected_delta,
                        error_rate,
                    });
                }
            }
        }

        // Update state
        state.previous_downstream.insert(channel.channel_id, channel.clone());
    }

    // If any channel triggered the error threshold, create a single anomaly
    if !triggered_channels.is_empty() {
        anomalies.push(ChannelAnomaly::HighErrorRate {
            threshold: thresholds.error_rate_threshold,
            triggered_channels,
        });
    }

    anomalies
}

pub fn check_upstream_channels(
    channels: &[UpstreamChannel],
    state: &mut ChannelState,
    thresholds: &ChannelThresholds,
) -> Vec<ChannelAnomaly> {
    let mut anomalies = Vec::new();

    for channel in channels {
        // Check signal strength
        if channel.signal_strength < thresholds.upstream_signal_min
            || channel.signal_strength > thresholds.upstream_signal_max
        {
            anomalies.push(ChannelAnomaly::UpstreamSignalOutOfRange {
                channel_id: channel.channel_id,
                signal: channel.signal_strength,
                min: thresholds.upstream_signal_min,
                max: thresholds.upstream_signal_max,
            });
        }

        // Update state
        state.previous_upstream.insert(channel.channel_id, channel.clone());
    }

    anomalies
}
