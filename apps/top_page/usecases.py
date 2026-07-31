"""top_pageアプリのユースケース（views.pyから呼び出される処理本体）"""

from . import weather
from .forms import MessageDisplayForm

MESSAGE_TEXTS = {
    "flash_debug": "これはデバッグレベルのフラッシュメッセージです",
    "flash_info": "これはインフォレベルのフラッシュメッセージです",
    "flash_success": "これはサクセスレベルのフラッシュメッセージです",
    "flash_warning": "これはワーニングレベルのフラッシュメッセージです",
    "flash_error": "これはエラーレベルのフラッシュメッセージです",
    "debug_message": "これはデバッグメッセージです",
}
HELLO_MESSAGE = "Hello jkmomo!"


def get(params, app_title):
    """トップページの表示処理"""
    return {
        "app_title": app_title,
        "hello_message": HELLO_MESSAGE,
        "message_form": MessageDisplayForm(),
        "weather_forecast": weather.get_three_day_forecast(),
    }


def post(request, app_title):
    pass
