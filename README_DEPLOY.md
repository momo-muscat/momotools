# momoTools 本番デプロイ手順

環境構築（`README_VPS.md`参照）完了後、コードの変更を本番に反映する際の日々の更新手順。

## 通常のアップデート手順

1. 開発機側でコミット・pushしておく。
2. VPSにSSH接続し、以下を実行する。

```bash
cd ~/momotools
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

3. `https://jkmomo.net/momotools/` 等で動作確認する。

> 本番での起動・再起動は必ず `-f docker-compose.yml -f docker-compose.prod.yml` を付けて実行する（付け忘れると開発用の`runserver`で起動してしまう）。

## マイグレーションを伴わない軽微な変更の場合

静的ファイルやテンプレートのみの変更であれば`migrate`は省略可。ただし`models.py`を変更した場合は必ず`migrate`を実行する。

## nginx設定自体を変更した場合

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## ロールバックする場合

```bash
git log --oneline
git checkout <戻したいコミットハッシュ>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec web python manage.py migrate
```
