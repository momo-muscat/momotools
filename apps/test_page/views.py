from django.shortcuts import redirect, render
from django.views import View

from . import usecases


class TestPageView(View):
    template_name = "test_page/index.html"
    app_title = "テストページ"

    def get(self, request, *args, **kwargs):
        context = usecases.index(request.GET, app_title=self.app_title)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        usecases.display_message(request, app_title=self.app_title)
        # POST後にそのままrenderすると再読み込み時にフォームが再送信されてしまうため、
        # Post/Redirect/GetパターンでGETへリダイレクトする
        return redirect("test_page:index")
