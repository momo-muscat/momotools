from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from . import usecases


@method_decorator(login_required, name="dispatch")
class AccountListView(View):
    template_name = "account_list/index.html"
    app_title = "アカウント一覧"

    def get(self, request, *args, **kwargs):
        context = usecases.get(request.GET, app_title=self.app_title)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        usecases.post(request, app_title=self.app_title)
        # POST後にそのままrenderすると再読み込み時にフォームが再送信されてしまうため、
        # Post/Redirect/GetパターンでGETへリダイレクトする
        return redirect("account_list:index")
