use crate::api::EventLog;
use chrono::{Datelike, NaiveDateTime};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// Identity of an event log entry for dedup purposes. The modem's `index`
/// field is a position in the rolling log and shifts as entries age out,
/// so the (time, type, event) triple is the stable identity.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct EventKey {
    pub time: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub event: String,
}

impl From<&EventLog> for EventKey {
    fn from(event: &EventLog) -> Self {
        Self {
            time: event.time.clone(),
            event_type: event.event_type.clone(),
            event: event.event.clone(),
        }
    }
}

/// Events logged before the modem syncs time-of-day are stamped with the
/// Unix epoch in the modem's local timezone (e.g. "12/31/69 19:01:07").
/// chrono's %y pivot maps 69 to 2069 and 70-99 to the 1970s-90s, so any
/// parsed year outside [2000, 2069) marks a pre-sync timestamp.
pub fn is_pre_sync_timestamp(ts: &NaiveDateTime) -> bool {
    !(2000..2069).contains(&ts.year())
}

/// Events in `current` that were not present in the previous snapshot.
pub fn new_events<'a>(current: &'a [EventLog], seen: &HashSet<EventKey>) -> Vec<&'a EventLog> {
    current
        .iter()
        .filter(|event| !seen.contains(&EventKey::from(*event)))
        .collect()
}

/// Snapshot of the current event log for the next poll's dedup.
pub fn snapshot(events: &[EventLog]) -> HashSet<EventKey> {
    events.iter().map(EventKey::from).collect()
}

/// Parse state-file contents (a JSON array of event keys). Legacy state
/// files held a bare timestamp; any unparseable content is treated as no
/// state so the monitor starts fresh.
pub fn parse_state(contents: &str) -> Option<HashSet<EventKey>> {
    serde_json::from_str::<Vec<EventKey>>(contents)
        .ok()
        .map(|keys| keys.into_iter().collect())
}

/// Serialize the seen set for the state file, sorted for stable output.
pub fn serialize_state(seen: &HashSet<EventKey>) -> String {
    let mut keys: Vec<&EventKey> = seen.iter().collect();
    keys.sort();
    serde_json::to_string_pretty(&keys).expect("event keys serialize to JSON")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::EventPriority;

    fn event(index: u32, time: &str, event_type: &str, event: &str) -> EventLog {
        EventLog {
            index,
            time: time.to_string(),
            event_type: event_type.to_string(),
            priority: EventPriority::Notice,
            event: event.to_string(),
        }
    }

    fn parse(time: &str) -> NaiveDateTime {
        NaiveDateTime::parse_from_str(time, "%m/%d/%y %H:%M:%S").unwrap()
    }

    #[test]
    fn epoch_timestamps_are_pre_sync() {
        // Unix epoch as seen from EST; chrono parses this year as 2069
        assert!(is_pre_sync_timestamp(&parse("12/31/69 19:01:07")));
        // Unix epoch in UTC; chrono parses this year as 1970
        assert!(is_pre_sync_timestamp(&parse("01/01/70 00:00:20")));
        assert!(is_pre_sync_timestamp(&parse("12/31/99 23:59:59")));
    }

    #[test]
    fn real_timestamps_are_not_pre_sync() {
        assert!(!is_pre_sync_timestamp(&parse("06/27/26 15:23:34")));
        assert!(!is_pre_sync_timestamp(&parse("01/01/00 00:00:00")));
        assert!(!is_pre_sync_timestamp(&parse("12/31/68 23:59:59")));
    }

    #[test]
    fn same_second_events_are_distinct() {
        // The old timestamp-based dedup could not tell these apart
        let events = vec![
            event(1, "06/27/26 15:23:34", "82001100", "RNG-RSP Power Exceeds DRW"),
            event(2, "06/27/26 15:23:34", "73050400", "REG-RSP-MP Mismatch"),
        ];
        let seen: HashSet<EventKey> = [EventKey::from(&events[0])].into();
        let new = new_events(&events, &seen);
        assert_eq!(new.len(), 1);
        assert_eq!(new[0].event_type, "73050400");
    }

    #[test]
    fn seen_events_are_not_new_regardless_of_timestamp() {
        // Epoch-stamped events must not reappear once seen, even though
        // chrono parses their year as 2069 (always "in the future")
        let events = vec![
            event(1, "06/27/26 15:23:34", "82001100", "RNG-RSP"),
            event(4, "12/31/69 19:01:07", "90000006", "CM Reboot Reason : POWER_ON"),
        ];
        let seen = snapshot(&events);
        assert!(new_events(&events, &seen).is_empty());
    }

    #[test]
    fn index_does_not_affect_identity() {
        // The same entry shifted down the rolling log is not a new event
        let seen = snapshot(&[event(1, "06/27/26 15:23:34", "82001100", "RNG-RSP")]);
        let shifted = vec![event(3, "06/27/26 15:23:34", "82001100", "RNG-RSP")];
        assert!(new_events(&shifted, &seen).is_empty());
    }

    #[test]
    fn state_round_trips() {
        let seen = snapshot(&[
            event(1, "06/27/26 15:23:34", "82001100", "RNG-RSP"),
            event(2, "12/31/69 19:01:07", "90000006", "POWER_ON"),
        ]);
        assert_eq!(parse_state(&serialize_state(&seen)), Some(seen));
    }

    #[test]
    fn legacy_timestamp_state_starts_fresh() {
        assert_eq!(parse_state("06/27/26 15:23:34"), None);
        assert_eq!(parse_state(""), None);
    }
}
