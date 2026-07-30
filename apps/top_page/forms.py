from django import forms

MESSAGE_CHOICES = [
    ("flash_debug", "フラッシュメッセージ（debug）"),
    ("flash_info", "フラッシュメッセージ（info）"),
    ("flash_success", "フラッシュメッセージ（success）"),
    ("flash_warning", "フラッシュメッセージ（warning）"),
    ("flash_error", "フラッシュメッセージ（error）"),
    ("debug_message", "デバッグメッセージ"),
]


class MessageDisplayForm(forms.Form):
    message_type = forms.ChoiceField(label="表示するメッセージ", choices=MESSAGE_CHOICES)
