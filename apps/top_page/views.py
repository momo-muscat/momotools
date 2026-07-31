from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from . import usecases


@method_decorator(login_required, name="dispatch")
class TopPageView(View):
    template_name = "top_page/index.html"
    app_title = "momoToolsトップページ"

    def get(self, request, *args, **kwargs):
        context = usecases.get(request.GET, app_title=self.app_title)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        usecases.post(request, app_title=self.app_title)
        # POST後にそのままrenderすると再読み込み時にフォームが再送信されてしまうため、
        # Post/Redirect/GetパターンでGETへリダイレクトする
        return redirect("top_page:index")
