use crate::api::{DownstreamChannel, UpstreamChannel};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct ChannelThresholds {
    pub downstream_snr_min: f64,
    pub downstream_signal_min: f64,
    pub downstream_signal_max: f64,
    pub upstream_signal_min: f64,
    pub upstream_signal_max: f64,
    pub uncorrectable_error_increase: i64,
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
            uncorrectable_error_increase: 100,  // Alert if uncorrectable errors increase by 100
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
    UncorrectableErrorIncrease {
        channel_id: u32,
        previous_errors: i64,
        current_errors: i64,
        increase: i64,
        threshold: i64,
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
            ChannelAnomaly::UncorrectableErrorIncrease { channel_id, previous_errors, current_errors, increase, threshold } => {
                write!(f, "Channel {} uncorrectable errors increased: {} → {} (+{}, threshold: {})",
                    channel_id, previous_errors, current_errors, increase, threshold)
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

        // Check for uncorrectable error increases
        if let Some(prev) = state.previous_downstream.get(&channel.channel_id) {
            let error_increase = channel.uncorrect - prev.uncorrect;
            if error_increase > thresholds.uncorrectable_error_increase {
                anomalies.push(ChannelAnomaly::UncorrectableErrorIncrease {
                    channel_id: channel.channel_id,
                    previous_errors: prev.uncorrect,
                    current_errors: channel.uncorrect,
                    increase: error_increase,
                    threshold: thresholds.uncorrectable_error_increase,
                });
            }
        }

        // Update state
        state.previous_downstream.insert(channel.channel_id, channel.clone());
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
