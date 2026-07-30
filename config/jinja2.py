from django.templatetags.static import static
from django.urls import reverse

from common.utilities import (
    debug_message_color,
    flash_message_color,
    get_debug_message,
    get_flash_messages,
)
from config.constants import FLASH_MESSAGE_DISPLAY_SECONDS
from jinja2 import Environment


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "get_flash_messages": get_flash_messages,
            "flash_message_color": flash_message_color,
            "get_debug_message": get_debug_message,
            "debug_message_color": debug_message_color,
            "FLASH_MESSAGE_DISPLAY_SECONDS": FLASH_MESSAGE_DISPLAY_SECONDS,
        }
    )
    return env
