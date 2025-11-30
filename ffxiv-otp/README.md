# ffxiv-otp

Generate and send TOTP codes to remote FFXIV launcher instances.

## Overview

This Rust application generates TOTP (Time-based One-Time Password) codes and sends them to a remote FFXIV launcher via HTTP. It's designed to automate OTP authentication for Final Fantasy XIV across multiple hosts.

## Features

- TOTP code generation using SHA1 algorithm
- Configuration-based host management with nicknames
- Secure credential storage using XDG directories
- Automated HTTP delivery to remote launcher instances

## Configuration

Create a configuration file at `~/.config/ffxiv-otp/config.toml`:

```toml
totp_secret = "YOUR_BASE32_TOTP_SECRET"

[hosts]
nickname1 = "hostname1.example.com"
nickname2 = "192.168.1.100"
```

## Usage

```bash
ffxiv-otp <nickname>
```

Where `<nickname>` is a host defined in your config file.

## How It Works

1. Reads TOTP secret and host mapping from config
2. Generates a 6-digit TOTP code (30-second validity)
3. Makes HTTP GET request to `http://<hostname>:4646/ffxivlauncher/<code>`
4. Displays the generated code and response status

## Dependencies

- `clap` - Command-line argument parsing
- `serde` + `toml` - Configuration file parsing
- `totp-rs` - TOTP generation
- `reqwest` - HTTP client
- `xdg` - XDG directory support
- `base32` - Base32 decoding for TOTP secret

## Building

```bash
cargo build --release
```
