"""Entrypoints — installed as the `minihermes` command (and `python -m minihermes`):

  minihermes                       chat in the terminal (default)
  minihermes dashboard             the browser cockpit → localhost:7777 (+ Telegram if configured)
  minihermes voice                 talk to it (needs the [voice] extra)
  minihermes telegram              phone → laptop (needs TELEGRAM_BOT_TOKEN)
  minihermes brief                 morning briefing (calendar + mail + memory)
  minihermes skill install <url>   install a community skill
"""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if not args:
        from minihermes.gateway.cli import main as cli_main

        cli_main()
    elif args[0] == "dashboard":
        from minihermes.ops.dashboard import main as dash_main

        dash_main()
    elif args[0] == "voice":
        from minihermes.gateway.voice import main as voice_main

        voice_main()
    elif args[0] == "telegram":
        from minihermes.gateway.telegram import main as tg_main

        tg_main()
    elif args[0] == "brief":
        from minihermes.ops.brief import main as brief_main

        brief_main()
    elif args[0] == "skill" and len(args) >= 3 and args[1] == "install":
        from minihermes.memory.procedural.installer import install

        install(args[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
