"""test_pageアプリのユースケース（views.pyから呼び出される処理本体）"""

from django.contrib import messages

from common.utilities import set_debug_message

from .forms import MessageDisplayForm

MESSAGE_TEXTS = {
    "flash_debug": "これはデバッグレベルのフラッシュメッセージです",
    "flash_info": "これはインフォレベルのフラッシュメッセージです",
    "flash_success": "これはサクセスレベルのフラッシュメッセージです",
    "flash_warning": "これはワーニングレベルのフラッシュメッセージです",
    "flash_error": "これはエラーレベルのフラッシュメッセージです",
    "debug_message": "これはデバッグメッセージです",
}
HELLO_MESSAGE = ""


def get(params, app_title):
    """テストページの表示処理"""
    return {
        "app_title": app_title,
        "hello_message": HELLO_MESSAGE,
        "message_form": MessageDisplayForm(),
    }


def post(request, app_title):
    """メッセージ表示フォームの送信処理。選択されたメッセージ種別ごとに表示する"""
    form = MessageDisplayForm(request.POST)
    if form.is_valid():
        message_type = form.cleaned_data["message_type"]
        text = MESSAGE_TEXTS[message_type]
        if message_type == "flash_debug":
            messages.debug(request, text)
        elif message_type == "flash_info":
            messages.info(request, text)
        elif message_type == "flash_success":
            messages.success(request, text)
        elif message_type == "flash_warning":
            messages.warning(request, text)
        elif message_type == "flash_error":
            messages.error(request, text)
        elif message_type == "debug_message":
            set_debug_message(request, text)
