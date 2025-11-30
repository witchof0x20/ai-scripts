# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of independent utility scripts and tools, each in its own subdirectory. Each tool solves a specific automation or monitoring need. The repository uses Nix flakes for reproducible builds and NixOS modules for deployment.

## Repository Structure

The repository contains these independent tools:

- **cal-upload/** - Python script to upload ICS calendar events from clipboard to Nextcloud via CalDAV
- **ffxiv-otp/** - Rust CLI tool that generates TOTP codes and sends them to remote FFXIV launcher instances
- **gradescope-utils/** - Python utilities for Gradescope automation (copying assignment extensions)
- **hitron/** - Contains both a Python diagnostic script (`modeminfo.py`) and a Rust monitoring daemon (`hitron-monitor`)
- **reminder/** - Python script that sends task reminders to Discord on a schedule
- **whenisgood/** - Python optimizer for office hours scheduling based on student availability

## Building and Running

### Nix Flake Commands

The repository uses a Nix flake for all build and development tasks:

```bash
# Build individual packages
nix build .#cal-upload
nix build .#reminder
nix build .#hitron-modeminfo        # Python diagnostic script
nix build .#ffxiv-otp               # Rust TOTP tool
nix build .#hitron-monitor          # Rust monitoring daemon
nix build .#gradescope-api

# Enter development shells
nix develop .#ffxiv-otp            # Rust dev environment with rust-analyzer, clippy, rustfmt
nix develop .#gradescope-utils     # Python environment with gradescope-api package

# Run tools directly
nix run .#cal-upload -- "Calendar Name"
nix run .#reminder -- --config tasks.json
nix run .#ffxiv-otp -- nickname
```

### Rust Projects

For Rust projects (ffxiv-otp, hitron-monitor), standard Cargo commands work within dev shells:

```bash
cd ffxiv-otp  # or hitron
nix develop  # enters environment with Rust toolchain

cargo build
cargo build --release
cargo test
cargo clippy
cargo fmt
```

### Python Scripts

Python scripts are standalone and can be run directly after installing dependencies:

```bash
# cal-upload
./cal-upload/cal_upload.py "Calendar Name"

# reminder
./reminder/reminder.py --config tasks.json

# hitron diagnostic tool
./hitron/modeminfo.py

# whenisgood scheduler
cd whenisgood
./solve_office_hours.py  # expects respondents.json and instructors.toml in current dir
```

## Architecture Notes

### Dual Hitron Tools

The `hitron/` directory contains two separate programs:

1. **modeminfo.py** - One-shot diagnostic script that retrieves and displays all modem information via HTTP API
2. **hitron-monitor** (Rust) - Long-running daemon that polls modem event logs and sends Discord notifications for signal issues

The Rust monitor is structured as:
- `api.rs` - HTTP client for modem API endpoints
- `monitor.rs` - Signal quality checking and event log polling logic
- `discord.rs` - Discord webhook notifications with embeds
- `main.rs` - CLI argument parsing and main loop

### NixOS Module Integration

Two tools have NixOS modules for system deployment:

- **reminder/module.nix** - Creates systemd timer + service for scheduled Discord reminders
- **hitron/module.nix** - Creates systemd service for continuous modem monitoring with configurable signal thresholds

These modules expose all configuration as NixOS options and include security hardening (DynamicUser, filesystem restrictions, etc.).

### Configuration Patterns

Tools use different configuration approaches:

- **XDG directories**: ffxiv-otp, cal-upload store config in `~/.config/<toolname>/`
- **Environment variables**: reminder, hitron-monitor, gradescope-utils read secrets from env vars
- **TOML files**: whenisgood uses `instructors.toml` for constraints, ffxiv-otp uses `config.toml`
- **JSON files**: whenisgood uses `respondents.json` for student data, reminder uses `tasks.json`

### Office Hours Scheduler Algorithm

The whenisgood scheduler has a multi-stage optimization approach:

1. Schedule all guaranteed (fixed) office hours first
2. Process instructors in TOML order (seniority-based priority)
3. For flexible hours, find continuous blocks that maximize student coverage
4. Respect per-instructor constraints (working hours, unavailable times, max block length)
5. Validate final schedule for conflicts and constraint violations

## Adding New Tools

When adding new utilities to this repository:

1. Create a subdirectory for the tool
2. Add README.md documenting usage, config, dependencies
3. Add package definition to `flake.nix` outputs
4. For Python: create `default.nix` for nixpkgs packaging
5. For Rust: use crane in flake.nix, add dependencies to deps attribute set
6. For system services: add optional `module.nix` with systemd service definition
