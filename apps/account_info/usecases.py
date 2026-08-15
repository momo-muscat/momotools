"""account_infoアプリのユースケース（views.pyから呼び出される処理本体）"""

from itertools import groupby

from django.contrib import messages
from django.shortcuts import get_object_or_404, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

from common.models import AccountList

from .forms import AccountForm, AccountSearchForm

NOT_FOUND_MESSAGE = "対象のアカウントが見つかりませんでした（既に削除された可能性があります）"
INDEX_URL = "account_info:index"


def get(params, app_title):
    """アカウント一覧の検索フォーム・検索結果表示処理"""
    search_form = AccountSearchForm(params) if params else AccountSearchForm()
    context = {
        "app_title": app_title,
        "sub_title": "一覧表示",
        "search_form": search_form,
    }
    if params:
        context["account_groups"] = _search(search_form)
    return context


def _search(search_form):
    """検索フォームの入力値でAccountListを絞り込み、区分ごとにグループ化する"""
    queryset = AccountList.objects.order_by("class_id", "name")
    if search_form.is_valid():
        account_class = search_form.cleaned_data["account_class"]
        account_name = search_form.cleaned_data["account_name"]
        under_contract = search_form.cleaned_data["under_contract"]
        if account_class:
            queryset = queryset.filter(class_id=account_class)
        if account_name:
            queryset = queryset.filter(name__icontains=account_name)
        # 契約中＝True は del_flg＝False のアカウントを指す
        if under_contract:
            queryset = queryset.filter(del_flg=False)
        else:
            queryset = queryset.filter(del_flg=True)

    groups = []
    for _, rows in groupby(queryset, key=lambda account: account.class_id):
        rows = list(rows)
        groups.append({"class_name": rows[0].class_name, "accounts": rows})
    return groups


def _safe_next_url(request, next_url):
    """遷移元へ安全に戻れる場合のみnext_urlを返す（外部サイトへのリダイレクトを防ぐ）"""
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def crud_get(request, app_title):
    """アカウントの新規追加・詳細画面の表示処理"""
    pk = request.GET.get("pk")
    if pk:
        account = get_object_or_404(AccountList, pk=pk)
        account_form = AccountForm(instance=account)
        is_new = False
    else:
        account_form = AccountForm(instance=AccountList())
        is_new = True
    return {
        "app_title": app_title,
        "sub_title": "新規追加" if is_new else "更新",
        "account_form": account_form,
        "is_new": is_new,
        "pk": pk,
        # 検索結果画面から遷移してきた場合、そのURLを保持して「戻る」で復元する
        "next_url": _safe_next_url(request, request.GET.get("next")),
    }


def crud_post(request, app_title):
    """アカウントの新規追加・更新・削除処理

    バリデーションエラー時は再表示用のコンテキスト（dict）を返す。
    それ以外（成功・対象なしエラー）はリダイレクト先URL（str）を返す。
    """
    pk = request.POST.get("pk")
    action = request.POST.get("action")
    safe_next_url = _safe_next_url(request, request.POST.get("next"))
    redirect_url = safe_next_url or resolve_url(INDEX_URL)

    if action == "delete":
        try:
            account = AccountList.objects.get(pk=pk)
        except AccountList.DoesNotExist:
            messages.error(request, NOT_FOUND_MESSAGE)
            return redirect_url
        account.delete()
        return redirect_url

    is_new = not pk
    instance = AccountList()
    if pk:
        try:
            instance = AccountList.objects.get(pk=pk)
        except AccountList.DoesNotExist:
            messages.error(request, NOT_FOUND_MESSAGE)
            return redirect_url

    account_form = AccountForm(request.POST, instance=instance)
    if not account_form.is_valid():
        return {
            "app_title": app_title,
            "sub_title": "新規追加" if is_new else "更新",
            "account_form": account_form,
            "is_new": is_new,
            "pk": pk,
            "next_url": safe_next_url,
        }
    account_form.save()
    return redirect_url
