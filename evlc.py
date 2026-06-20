#!/usr/bin/env python3
"""Enqueue files and URLs into VLC without cmd.exe re-parsing the arguments."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
SCRIPT_DIR = Path(__file__).resolve().parent
LOGGING_ENABLED = True
LOG_FILE = SCRIPT_DIR / "VLC-enqueued.log"
RC_HOST = "127.0.0.1"
RC_PORT = 4212


def find_vlc() -> str:
    candidates = [
        os.environ.get("VLC_EXE"),
        shutil.which("vlc.exe"),
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("evlc: VLC not found. Set VLC_EXE or install VLC in the default location.")


def clean_url(url: str) -> str:
    return url.rstrip(".;]")


def expand_items(args: list[str]) -> list[str]:
    items: list[str] = []
    for arg in args:
        text = arg.strip().strip('"')
        if not text:
            continue

        # Preserve VLC command-line options verbatim. Some options contain URLs
        # (for example --http-referrer=https://...), and those URLs are values,
        # not additional media items to enqueue.
        if text.startswith("-"):
            items.append(text)
            continue

        urls = [clean_url(match.group(0)) for match in URL_RE.finditer(text)]
        if urls:
            items.extend(urls)
        else:
            items.append(text)
    return items


def prepare_vlc_args(args: list[str]) -> list[str]:
    """Put extension-supplied HTTP metadata after each media item."""
    expanded = expand_items(args)
    global_options: list[str] = []
    media: list[str] = []
    item_options: list[str] = []
    index = 0

    while index < len(expanded):
        arg = expanded[index]
        if arg in ("--http-referrer", "--http-user-agent"):
            if index + 1 < len(expanded):
                item_options.append(f":{arg[2:]}={expanded[index + 1]}")
                index += 2
                continue
        elif arg.startswith("--http-referrer=") or arg.startswith("--http-user-agent="):
            item_options.append(f":{arg[2:]}")
            index += 1
            continue
        elif arg.startswith(":"):
            item_options.append(arg)
            index += 1
            continue
        elif arg.startswith("-"):
            global_options.append(arg)
            index += 1
            continue

        media.append(arg)
        index += 1

    prepared = list(global_options)
    for item in media:
        prepared.append(item)
        prepared.extend(item_options)
    return prepared


def iter_media_items(args: list[str]) -> list[list[str]]:
    """Group each media item with its following colon-prefixed input options."""
    grouped: list[list[str]] = []
    for arg in args:
        if arg.startswith(":") and grouped:
            grouped[-1].append(arg)
        elif not arg.startswith("-"):
            grouped.append([arg])
    return grouped


def enqueue_via_rc(args: list[str]) -> bool:
    """Enqueue directly into an EVLC-started VLC instance."""
    items = iter_media_items(args)
    if not items:
        return False

    commands_sent = False
    try:
        with socket.create_connection((RC_HOST, RC_PORT), timeout=0.75) as connection:
            connection.settimeout(2.0)
            for item in items:
                command = "enqueue " + " ".join(item)
                if "\r" in command or "\n" in command:
                    raise ValueError("Media arguments must not contain newlines")
                connection.sendall(command.encode("utf-8") + b"\n")
            # Ask VLC to close this RC client cleanly, then consume its replies.
            # Closing a Windows socket with unread replies can send a reset and
            # make VLC process only the first of several queued commands.
            connection.sendall(b"logout\n")
            connection.shutdown(socket.SHUT_WR)
            commands_sent = True
            while connection.recv(4096):
                pass
        return True
    except socket.timeout:
        # The commands were sent successfully; some VLC builds keep the RC
        # connection open briefly even after processing "logout".
        return commands_sent
    except (OSError, ValueError):
        return False


def log_items(items: list[str]) -> None:
    if not LOGGING_ENABLED:
        return

    with LOG_FILE.open("a", encoding="utf-8") as log:
        for item in items:
            log.write(f"{item}\n")


def main(argv: list[str]) -> int:
    dry_run = False
    if "--dry-run" in argv:
        dry_run = True
        argv = [arg for arg in argv if arg != "--dry-run"]
    items = prepare_vlc_args(argv)
    if not items:
        print("Usage: evlc URL_OR_FILE [URL_OR_FILE ...]", file=sys.stderr)
        return 2

    vlc = find_vlc()
    command = [
        vlc,
        "--one-instance",
        "--playlist-enqueue",
        "--extraintf=oldrc",
        f"--rc-host={RC_HOST}:{RC_PORT}",
        "--rc-quiet",
        *items,
    ]
    if dry_run:
        print(command)
        return 0
    log_items(items)
    if enqueue_via_rc(items):
        return 0
    subprocess.Popen(command, close_fds=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
