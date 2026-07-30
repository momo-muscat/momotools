from django.urls import path

from .views import TestPageView

app_name = "test_page"

urlpatterns = [
    path("", TestPageView.as_view(), name="index"),
    path("index.html", TestPageView.as_view(), name="index_html"),
]
