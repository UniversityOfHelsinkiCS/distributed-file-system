import logging
import os

log_level_str = os.environ.get("LOG_LEVEL", "DEBUG").upper()
log_level = getattr(logging, log_level_str)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Disable default logging to avoid duplicate logs
logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
