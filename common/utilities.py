"""jinja2/common/base.html から利用する共通ユーティリティ"""

from django.contrib import messages

# メッセージレベル（message.level_tag）ごとの背景色（薄め）
FLASH_MESSAGE_COLORS = {
    "debug": "bg-orange-100 border-orange-300 text-orange-800",
    "info": "bg-green-100 border-green-300 text-green-800",
    "success": "bg-blue-100 border-blue-300 text-blue-800",
    "warning": "bg-yellow-100 border-yellow-300 text-yellow-800",
    "error": "bg-pink-100 border-pink-300 text-pink-800",
}
DEFAULT_FLASH_MESSAGE_COLOR = "bg-gray-100 border-gray-300 text-gray-800"


def get_flash_messages(request):
    """Messagesフレームワークに溜まっているメッセージを一覧で返す"""
    return list(messages.get_messages(request))


def flash_message_color(level_tag):
    """メッセージレベル（debug/info/success/warning/error）から背景色クラスを返す"""
    return FLASH_MESSAGE_COLORS.get(level_tag, DEFAULT_FLASH_MESSAGE_COLOR)


# デバッグメッセージ（Messagesフレームワークは使用せず、セッションに設定したテキストを表示する）
DEBUG_MESSAGE_SESSION_KEY = "debug_message"
DEBUG_MESSAGE_COLOR = "bg-orange-100 border-orange-300 text-orange-800"


def get_debug_message(request):
    """セッションに設定されているデバッグメッセージを取り出す（一度表示したら消える）"""
    return request.session.pop(DEBUG_MESSAGE_SESSION_KEY, "")


def set_debug_message(request, text):
    """デバッグメッセージをセッションに設定する"""
    request.session[DEBUG_MESSAGE_SESSION_KEY] = text


def debug_message_color():
    """デバッグメッセージの背景色クラスを返す"""
    return DEBUG_MESSAGE_COLOR
