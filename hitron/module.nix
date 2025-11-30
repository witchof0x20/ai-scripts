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
            args = [ "--interval" (toString cfg.pollInterval) ]
              ++ (optionals (cfg.roleId != null) [ "--role" (toString cfg.roleId) ]);
            argString = concatStringsSep " " args;
          in
          "${hitron-monitor}/bin/hitron-monitor ${argString}";
        DynamicUser = true;

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
