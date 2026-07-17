from django.views.generic import TemplateView


class TopPageView(TemplateView):
    template_name = "top_page/index.html"
