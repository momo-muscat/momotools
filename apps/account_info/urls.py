from django.urls import path

from .views import AccountCrudView, AccountListView

app_name = "account_info"

urlpatterns = [
    path("", AccountListView.as_view(), name="index"),
    path("index.html", AccountListView.as_view(), name="index_html"),
    path("crud.html", AccountCrudView.as_view(), name="crud"),
]
