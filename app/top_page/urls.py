from django.urls import path

from .views import TopPageView

app_name = "top_page"

urlpatterns = [
    path("", TopPageView.as_view(), name="index"),
    path("index.html", TopPageView.as_view(), name="index_html"),
]
