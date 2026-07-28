# momoTools 本番デプロイ手順

環境構築（`README_VPS.md`参照）完了後、コードの変更を本番に反映する際の日々の更新手順。

## 通常のアップデート手順

1. 開発機側でコミット・pushしておく。
2. VPSにSSH接続し、以下を実行する。

```bash
cd ~/momotools
git pull
uv sync
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
sudo systemctl restart momotools
```

3. `https://jkmomo.net/momotools/` 等で動作確認する。

```bash
sudo systemctl status momotools
journalctl -u momotools -n 50 --no-pager
```

## マイグレーションを伴わない軽微な変更の場合

静的ファイルやテンプレートのみの変更であれば`migrate`は省略可。ただし`models.py`を変更した場合は必ず`migrate`を実行する。
依存関係(`pyproject.toml`/`uv.lock`)に変更が無ければ`uv sync`も省略可。

## nginx設定自体を変更した場合

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## ロールバックする場合

```bash
git log --oneline
git checkout <戻したいコミットハッシュ>
uv sync
uv run python manage.py migrate
sudo systemctl restart momotools
```
