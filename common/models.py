from django.db import models
from django.db.models.functions import Now


class AccountClass(models.Model):
    """アカウント区分"""

    code = models.IntegerField(
        unique=True,
        verbose_name="区分ID",
        db_comment="区分ID",
        default=0,
        db_default=0,
    )
    name = models.CharField(
        max_length=100,
        verbose_name="区分名",
        db_comment="区分名",
        default="区分名",
        db_default="区分名",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="登録日時", db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時", db_default=Now())

    class Meta:
        db_table = "account_class"
        db_table_comment = "アカウント区分"
        verbose_name = "アカウント区分"

    def __str__(self):
        return self.name


class AccountList(models.Model):
    """アカウント一覧"""

    name = models.CharField(
        max_length=100,
        verbose_name="アカウント名",
        db_comment="アカウント名",
        default="アカウント名",
        db_default="アカウント名",
    )
    class_id = models.IntegerField(
        verbose_name="区分ID",
        db_comment="区分ID",
        default=0,
        db_default=0,
    )
    class_name = models.CharField(
        max_length=100,
        verbose_name="区分名",
        db_comment="区分名",
        default="区分名",
        db_default="区分名",
    )
    login_url = models.CharField(
        max_length=200,
        verbose_name="ログインURL",
        db_comment="ログインURL",
        default="ログインURL",
        db_default="ログインURL",
    )
    user_id = models.CharField(
        max_length=20,
        verbose_name="ユーザID",
        db_comment="ユーザID",
        default="ユーザID",
        db_default="ユーザID",
    )
    password = models.CharField(
        max_length=50,
        verbose_name="パスワード",
        db_comment="パスワード",
        default="パスワード",
        db_default="パスワード",
    )
    del_flg = models.BooleanField(
        verbose_name="削除フラグ", db_comment="削除フラグ", default=False, db_default=False
    )
    member_id = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="会員ID",
        db_comment="会員ID",
        default="",
        db_default="",
    )
    status1 = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="ステータス1",
        db_comment="ステータス1",
        default="",
        db_default="",
    )
    status2 = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="ステータス2",
        db_comment="ステータス2",
        default="",
        db_default="",
    )
    memo = models.TextField(
        blank=True,
        verbose_name="メモ",
        db_comment="メモ",
        default="",
        db_default="",
    )
    company_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="会社名",
        db_comment="会社名",
        default="",
        db_default="",
    )
    company_url = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="会社URL",
        db_comment="会社URL",
        default="",
        db_default="",
    )
    company_tel = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="会社TEL",
        db_comment="会社TEL",
        default="",
        db_default="",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="登録日時", db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時", db_default=Now())

    class Meta:
        db_table = "account_list"
        db_table_comment = "アカウント一覧"
        verbose_name = "アカウント一覧"

    def __str__(self):
        return self.name
