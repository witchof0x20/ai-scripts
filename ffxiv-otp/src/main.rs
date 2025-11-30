use base32::Alphabet;
use clap::Parser;
use serde::Deserialize;
use std::collections::HashMap;
use totp_rs::{Algorithm, TOTP};
use xdg::BaseDirectories;
use std::io;

#[derive(Parser)]
#[command(author, version, about)]
struct Args {
    nickname: String,
}

#[derive(Deserialize)]
struct Config {
    totp_secret: String,
    hosts: HashMap<String, String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Set up XDG paths
    let xdg_dirs = BaseDirectories::with_prefix("ffxiv-otp");
    let config_path = xdg_dirs
        .get_config_file("config.toml")
        .ok_or(io::Error::new(
            io::ErrorKind::NotFound,
            "Config file not found",
        ))?;

    // Read and parse config
    let config_str = std::fs::read_to_string(config_path)?;
    let config: Config = toml::from_str(&config_str)?;

    // Look up hostname
    let hostname = config
        .hosts
        .get(&args.nickname)
        .ok_or("Nickname not found in config")?;

    // Generate TOTP
    let totp = TOTP::new(
        Algorithm::SHA1,
        6,
        1,
        30,
        base32::decode(Alphabet::Rfc4648 { padding: false }, &config.totp_secret).ok_or(
            io::Error::new(io::ErrorKind::InvalidData, "Invalid TOTP secret"),
        )?,
    )?;

    let code = totp.generate_current()?;
    println!("Code is {code}");
    // Make HTTP request
    let url = format!("http://{}:4646/ffxivlauncher/{}", hostname, code);
    let client = reqwest::blocking::Client::new();
    let response = client.get(&url).send()?;

    println!("Response status: {}", response.status());

    Ok(())
}
