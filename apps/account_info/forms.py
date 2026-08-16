from django import forms

from common.models import AccountClass, AccountList


class AccountSearchForm(forms.Form):
    CONTRACT_STATUS_ALL = "all"
    CONTRACT_STATUS_ACTIVE = "active"
    CONTRACT_STATUS_CANCELLED = "cancelled"
    CONTRACT_STATUS_CHOICES = [
        (CONTRACT_STATUS_ALL, "すべて"),
        (CONTRACT_STATUS_ACTIVE, "契約中"),
        (CONTRACT_STATUS_CANCELLED, "解約"),
    ]

    account_class = forms.ChoiceField(label="区分", required=False, initial="")
    account_name = forms.CharField(label="アカウント名", required=False)
    under_contract = forms.ChoiceField(
        label="契約状態",
        required=False,
        choices=CONTRACT_STATUS_CHOICES,
        initial=CONTRACT_STATUS_ACTIVE,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account_class"].choices = [("", "すべて")] + [
            (account_class.code, account_class.name)
            for account_class in AccountClass.objects.order_by("code")
        ]


class AccountForm(forms.ModelForm):
    """アカウントの新規追加・詳細（更新）画面のフォーム"""

    account_class = forms.ChoiceField(label="区分")
    under_contract = forms.BooleanField(label="契約中", required=False, initial=True)

    class Meta:
        model = AccountList
        fields = [
            "name",
            "login_url",
            "user_id",
            "password",
            "member_id",
            "status1",
            "status2",
            "memo",
            "company_name",
            "company_url",
            "company_tel",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account_class"].choices = [
            (account_class.code, account_class.name)
            for account_class in AccountClass.objects.order_by("code")
        ]
        # フィールドの並び順を「区分」が先頭に来るよう調整する
        other_fields = [
            name for name in self.fields if name not in ("name", "account_class", "under_contract")
        ]
        self.order_fields(["name", "account_class", "under_contract", *other_fields])
        if self.instance.pk:
            self.fields["account_class"].initial = self.instance.class_id
            self.fields["under_contract"].initial = not self.instance.del_flg

    def save(self, commit=True):
        account = super().save(commit=False)
        account_class = AccountClass.objects.get(code=self.cleaned_data["account_class"])
        account.class_id = account_class.code
        account.class_name = account_class.name
        account.del_flg = not self.cleaned_data["under_contract"]
        if commit:
            account.save()
        return account
