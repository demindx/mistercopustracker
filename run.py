#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui.app import HeadTimerUI


def main():
    parser = argparse.ArgumentParser(
        description="MisterTimer — pin OBS widget to streamer's forehead"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="UI host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="UI port (default: 8080)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Listen on all interfaces (0.0.0.0)",
    )
    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host

    app = HeadTimerUI()
    app.run(host=host, port=args.port, show=not args.no_browser)


if __name__ == "__main__":
    main()
