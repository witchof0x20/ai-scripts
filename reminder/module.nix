packages: { config, lib, pkgs, ... }:
with lib;

let
  cfg = config.services.discord-reminder;
  reminder = packages.${config.nixpkgs.system}.reminder;
in
{
  options.services.discord-reminder = {
    enable = mkEnableOption "Discord reminder service";

    reminderTime = mkOption {
      type = types.str;
      example = "09:00";
      description = "Time to send reminders (24-hour format)";
    };

    tasks = mkOption {
      type = types.listOf types.str;
      default = [ ];
      example = [ "Check emails" "Team standup" ];
      description = "List of tasks to remind about";
    };

    webhookFile = mkOption {
      type = types.path;
      example = "/var/secrets/discord-webhook";
      description = "Path to file containing DISCORD_WEBHOOK_URL";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.discord-reminder = {
      description = "Discord Task Reminder";
      environment = {
        TASK_FILE = pkgs.writeText "tasks.toml" ''
          tasks = [
            ${concatMapStrings (task: ''"${task}",\n'') cfg.tasks}
          ]
        '';
      };
      serviceConfig = {
        Type = "oneshot";
        EnvironmentFile = cfg.webhookFile;
        ExecStart = "${reminder}/bin/discord-reminder -c $TASK_FILE";
        DynamicUser = true;
      };
    };

    systemd.timers.discord-reminder = {
      wantedBy = [ "timers.target" ];
      partOf = [ "discord-reminder.service" ];
      timerConfig = {
        OnCalendar = "*-*-* ${cfg.reminderTime}:00";
        Unit = "discord-reminder.service";
      };
    };
  };
}