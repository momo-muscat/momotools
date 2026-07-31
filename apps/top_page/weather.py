"""トップページに表示する天気予報（Open-Meteo APIを使用、APIキー不要）"""

import json
import urllib.error
import urllib.request
from datetime import datetime

import jpholiday
from django.core.cache import cache

# 岡山市の緯度・経度
LATITUDE = 34.6551
LONGITUDE = 133.9195

FORECAST_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min"
    "&timezone=Asia%2FTokyo&forecast_days=3"
)
CACHE_KEY = "top_page:weather_forecast:okayama"
CACHE_TIMEOUT_SECONDS = 30 * 60
REQUEST_TIMEOUT_SECONDS = 5

DAY_LABELS = ["今日", "明日", "明後日"]
WEEKDAY_KANJI = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_COLOR_HOLIDAY = "text-red-400"
WEEKDAY_COLOR_SATURDAY = "text-blue-400"
WEEKDAY_COLOR_DEFAULT = "text-gray-300"

# WMO Weather interpretation codesの日本語表記（よく使うものだけ）
WEATHER_CODE_LABELS = {
    0: ("快晴", "☀️"),
    1: ("晴れ", "🌤️"),
    2: ("晴れ時々曇り", "⛅"),
    3: ("曇り", "☁️"),
    45: ("霧", "🌫️"),
    48: ("霧", "🌫️"),
    51: ("霧雨", "🌦️"),
    53: ("霧雨", "🌦️"),
    55: ("霧雨", "🌦️"),
    56: ("着氷性の霧雨", "🌧️"),
    57: ("着氷性の霧雨", "🌧️"),
    61: ("小雨", "🌧️"),
    63: ("雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("着氷性の雨", "🌧️"),
    67: ("着氷性の雨", "🌧️"),
    71: ("小雪", "🌨️"),
    73: ("雪", "🌨️"),
    75: ("大雪", "🌨️"),
    77: ("霧雪", "🌨️"),
    80: ("にわか雨", "🌦️"),
    81: ("にわか雨", "🌦️"),
    82: ("激しいにわか雨", "⛈️"),
    85: ("にわか雪", "🌨️"),
    86: ("にわか雪", "🌨️"),
    95: ("雷雨", "⛈️"),
    96: ("雷雨（ひょう）", "⛈️"),
    99: ("雷雨（ひょう）", "⛈️"),
}
DEFAULT_WEATHER_LABEL = ("不明", "❓")


def _describe_weather_code(code):
    return WEATHER_CODE_LABELS.get(code, DEFAULT_WEATHER_LABEL)


def _format_date(date):
    """「8/1(土)」形式の表示文字列と、曜日・祝日に応じた文字色クラスを返す"""
    weekday = date.weekday()  # 月曜=0 ... 日曜=6
    display = f"{date.month}/{date.day}({WEEKDAY_KANJI[weekday]})"
    if jpholiday.is_holiday(date.date()) or weekday == 6:
        color_class = WEEKDAY_COLOR_HOLIDAY
    elif weekday == 5:
        color_class = WEEKDAY_COLOR_SATURDAY
    else:
        color_class = WEEKDAY_COLOR_DEFAULT
    return display, color_class


def _fetch_forecast():
    """Open-Meteo APIから3日分の予報を取得する。失敗時はNoneを返す"""
    try:
        with urllib.request.urlopen(FORECAST_API_URL, timeout=REQUEST_TIMEOUT_SECONDS) as res:
            data = json.load(res)
        daily = data["daily"]

        forecast = []
        for i, label in enumerate(DAY_LABELS):
            date = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            description, icon = _describe_weather_code(daily["weather_code"][i])
            date_display, date_color_class = _format_date(date)
            forecast.append(
                {
                    "label": label,
                    "date": date_display,
                    "date_color_class": date_color_class,
                    "icon": icon,
                    "description": description,
                    "temperature_max": round(daily["temperature_2m_max"][i]),
                    "temperature_min": round(daily["temperature_2m_min"][i]),
                }
            )
        return forecast
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None


def get_three_day_forecast():
    """3日分（今日・明日・明後日）の天気予報を返す（結果は30分キャッシュ）"""
    forecast = cache.get(CACHE_KEY)
    if forecast is None:
        forecast = _fetch_forecast()
        if forecast is not None:
            cache.set(CACHE_KEY, forecast, CACHE_TIMEOUT_SECONDS)
    return forecast
