packages: { config, lib, pkgs, ... }:
with lib;

let
  cfg = config.services.hitron-monitor;
  hitron-monitor = packages.${config.nixpkgs.system}.hitron-monitor;
in
{
  options.services.hitron-monitor = {
    enable = mkEnableOption "Hitron modem event monitoring service";

    webhookFile = mkOption {
      type = types.path;
      example = "/var/secrets/discord-webhook";
      description = "Path to file containing DISCORD_WEBHOOK environment variable";
    };

    pollInterval = mkOption {
      type = types.int;
      default = 60;
      example = 120;
      description = "Poll interval in seconds for checking modem events";
    };

    roleId = mkOption {
      type = types.nullOr types.int;
      default = null;
      example = 123456789012345678;
      description = "Discord role ID to ping when events occur (optional)";
    };

    downstreamSnrMin = mkOption {
      type = types.float;
      default = 33.0;
      description = "Minimum acceptable downstream SNR in dB (DOCSIS 3.0/3.1 recommendation: 33)";
    };

    downstreamSignalMin = mkOption {
      type = types.float;
      default = -9.0;
      description = "Minimum acceptable downstream signal strength in dBmV";
    };

    downstreamSignalMax = mkOption {
      type = types.float;
      default = 15.0;
      description = "Maximum acceptable downstream signal strength in dBmV";
    };

    upstreamSignalMin = mkOption {
      type = types.float;
      default = 37.0;
      description = "Minimum acceptable upstream signal strength in dBmV";
    };

    upstreamSignalMax = mkOption {
      type = types.float;
      default = 53.0;
      description = "Maximum acceptable upstream signal strength in dBmV";
    };

    errorRateThreshold = mkOption {
      type = types.float;
      default = 0.01;
      description = "Alert if error rate (uncorrected/(corrected+uncorrected)) exceeds this threshold (0.01 = 1%)";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.hitron-monitor = {
      description = "Hitron Modem Event Monitor";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        Type = "simple";
        Restart = "always";
        RestartSec = "10s";
        EnvironmentFile = cfg.webhookFile;
        ExecStart =
          let
            args = [ "--interval=${toString cfg.pollInterval}" ]
              ++ (optionals (cfg.roleId != null) [ "--role=${toString cfg.roleId}" ])
              ++ [ "--state-file=%S/hitron-monitor/last-index" ]
              ++ [ "--downstream-snr-min=${toString cfg.downstreamSnrMin}" ]
              ++ [ "--downstream-signal-min=${toString cfg.downstreamSignalMin}" ]
              ++ [ "--downstream-signal-max=${toString cfg.downstreamSignalMax}" ]
              ++ [ "--upstream-signal-min=${toString cfg.upstreamSignalMin}" ]
              ++ [ "--upstream-signal-max=${toString cfg.upstreamSignalMax}" ]
              ++ [ "--error-rate-threshold=${toString cfg.errorRateThreshold}" ];
            argString = concatStringsSep " " args;
          in
          "${hitron-monitor}/bin/hitron-monitor ${argString}";
        DynamicUser = true;
        StateDirectory = "hitron-monitor";

        # Security hardening
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [ "AF_INET" "AF_INET6" ];
        RestrictNamespaces = true;
        LockPersonality = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        PrivateDevices = true;
      };
    };
  };
}
