"""Single entry point: `python -m jobradar <command>`.

    python -m jobradar run [--dry-run]   # radar run
    python -m jobradar check             # check DOU/IMAP/scorer/Telegram
    python -m jobradar top [--limit N]   # best from the DB
    python -m jobradar stats             # collection funnel
    python -m jobradar serve [--port N]  # web interface

`serve` goes to the web layer (jobradar.app); everything else to the CLI core.
The core never imports the web layer, so the CLI stays light and the
web → core dependency stays one-directional.
"""

import sys


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "serve":
        from jobradar.app import main as serve_main

        # Drop 'serve' so the app's argparse sees only its own --host/--port.
        sys.argv = [sys.argv[0], *argv[1:]]
        return serve_main()

    from jobradar import cli

    return cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
