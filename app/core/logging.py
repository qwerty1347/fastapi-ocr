import inspect
import logging


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def get_logger() -> logging.Logger:
    frame = inspect.stack()[1]
    name = frame.frame.f_globals["__name__"]
    return logging.getLogger(name)