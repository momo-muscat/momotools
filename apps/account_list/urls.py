from django.urls import path

from .views import AccountListView

app_name = "account_list"

urlpatterns = [
    path("", AccountListView.as_view(), name="index"),
    path("index.html", AccountListView.as_view(), name="index_html"),
]
