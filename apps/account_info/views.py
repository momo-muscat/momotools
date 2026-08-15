from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from . import usecases


@method_decorator(login_required, name="dispatch")
class AccountListView(View):
    template_name = "account_info/index.html"
    app_title = "アカウント情報"

    def get(self, request, *args, **kwargs):
        context = usecases.get(request.GET, app_title=self.app_title)
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class AccountCrudView(View):
    template_name = "account_info/crud.html"
    app_title = "アカウント情報"

    def get(self, request, *args, **kwargs):
        context = usecases.crud_get(request.GET, app_title=self.app_title)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        context = usecases.crud_post(request, app_title=self.app_title)
        if context is not None:
            # バリデーションエラー時は入力内容を保持したまま同じ画面を再表示する
            return render(request, self.template_name, context)
        # 成功時・対象なしエラー時はPost/Redirect/Getパターンで一覧へ戻す
        return redirect("account_info:index")
