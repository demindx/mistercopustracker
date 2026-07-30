import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("nicegui").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    if debug:
        logging.getLogger().debug("Debug logging enabled")
