"""
Halloween/Christmas theming for terminal output.

Spooky colors, festive emojis, and Rich styling for the CLI.
"""

from __future__ import annotations

from rich.theme import Theme

# Halloween-Christmas color palette
SKELLINGTON_THEME = Theme(
    {
        "jack": "bold bright_white",
        "sally": "bold magenta",
        "oogie": "bold yellow",
        "zero": "bold cyan",
        "lock": "bold red",
        "shock": "bold purple",
        "barrel": "bold dark_orange",
        "mayor": "bold green",
        "success": "bold bright_green",
        "error": "bold bright_red",
        "warning": "bold yellow",
        "info": "bright_cyan",
        "dim": "dim white",
        "header": "bold bright_white on dark_red",
    }
)

AGENT_STYLES: dict[str, str] = {
    "jack": "jack",
    "sally": "sally",
    "oogie": "oogie",
    "zero": "zero",
    "lock": "lock",
    "shock": "shock",
    "barrel": "barrel",
    "mayor": "mayor",
}

AGENT_EMOJIS: dict[str, str] = {
    "jack": "🎃👔",
    "sally": "🧟‍♀️🎁",
    "oogie": "🎰🎅",
    "zero": "👻🔴",
    "lock": "👹",
    "shock": "🔮👹",
    "barrel": "💀👹",
    "mayor": "🎭📊",
}

BANNER = r"""
[header]
  _____ _        _ _ _             _
 / ____| |      | | (_)           | |
| (___ | | _____| | |_ _ __   __ _| |_ ___  _ __
 \___ \| |/ / _ \ | | | '_ \ / _` | __/ _ \| '_ \
 ____) |   <  __/ | | | | | | (_| | || (_) | | | |
|_____/|_|\_\___|_|_|_|_| |_|\__, |\__\___/|_| |_|
                               __/ |
    🎃 Halloween meets Christmas 🎄 |___/
[/header]
"""
