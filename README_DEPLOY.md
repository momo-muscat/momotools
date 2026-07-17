# momoTools 本番デプロイ手順（VPS / Ubuntu）

VPS上にmomoToolsを本番稼働させるための構築〜デプロイ手順を、実施した順に記録する。

## 前提

- VPS: 2コア / 2GB メモリ
- OS: Ubuntu 26.04 LTS (Resolute Raccoon)
- IPアドレス: 133.18.145.216
- SSHユーザー: ubuntu（鍵認証、ポート22）
- ドメイン: jkmomo.net
- 用途: 個人利用・友人公開程度（大量同時アクセスなし）
- 構成: Docker Compose上で `web`（Django + gunicorn）/ `db`（PostgreSQL）を稼働し、`nginx` でリバースプロキシ + TLS終端する想定

## 進捗

- [x] 1. VPSの初期設定
- [x] 2. Docker Engineのインストール
- [x] 3. リポジトリのクローン
- [x] 4. 本番用`.env`の作成
- [ ] 5. 本番向け設定の調整（DEBUG, ALLOWED_HOSTS, gunicorn化など）
- [ ] 6. nginx + Let's Encrypt(certbot)でのリバースプロキシ/TLS設定
- [ ] 7. コンテナの起動・自動起動設定
- [ ] 8. 動作確認
- [ ] 9. （任意）バックアップ運用

---

## 1. VPSの初期設定

```bash
cat /etc/os-release
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone Asia/Tokyo

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

結果：

```
PRETTY_NAME="Ubuntu 26.04 LTS"
VERSION="26.04 (Resolute Raccoon)"

Status: active
To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
OpenSSH (v6)               ALLOW       Anywhere (v6)
80/tcp (v6)                ALLOW       Anywhere (v6)
443/tcp (v6)               ALLOW       Anywhere (v6)
```

## 2. Docker Engineのインストール

`README.md`の「Linux環境構築手順 1.」と同じ手順（VPS上のubuntuユーザーで実行）。

```bash
# 既存パッケージの削除
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y $pkg
done

# 依存パッケージとDocker公式GPGキーの登録
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# リポジトリ登録
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker Engine + Compose pluginのインストール
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# sudoなしでdockerを使えるようにする
sudo usermod -aG docker $USER
```

> 反映には一度ログアウト→再ログイン（`exit`してSSH再接続）が必要。反映後 `docker run hello-world` で無鍵動作確認可能。

結果：`docker run hello-world` 成功（sudoなしで実行、Docker Engine正常動作確認）。
`apt upgrade`によりカーネル更新があり `System restart required` が出たため `sudo reboot` を実施。再起動後も動作確認済み。

## 3. リポジトリのクローン

```bash
git clone https://github.com/momo-muscat/momotools.git
cd momotools
```

結果：クローン成功（`~/momotools`配下に展開）。
また `docker run hello-world` は再起動後も sudo なしで正常動作を確認済み。

## 4. 本番用`.env`の作成

`.env`は`.gitignore`対象のためリポジトリに含まれない。VPS上で新規作成する。

```bash
cd ~/momotools
cp .env.example .env
```

`.env`の中身を本番用に編集する。

```bash
nano .env
```

以下の値を設定する：

```
DEBUG=False
DJANGO_SECRET_KEY=<新規生成した値に変更>
DJANGO_ALLOWED_HOSTS=jkmomo.net,www.jkmomo.net,133.18.145.216
DATABASE_URL=psql://momotools:<強力なパスワードに変更>@db:5432/momotools

POSTGRES_DB=momotools
POSTGRES_USER=momotools
POSTGRES_PASSWORD=<DATABASE_URLと同じ強力なパスワード>
```

`DJANGO_SECRET_KEY`は使い回さず、本番専用の値を新規生成する。以下のコマンドでランダムな値を生成できる。

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

生成された文字列を`DJANGO_SECRET_KEY`にコピーする。`POSTGRES_PASSWORD`も同様に推測されにくい値に変更し、`DATABASE_URL`内のパスワードと一致させる。

結果：作成・設定完了（`DJANGO_SECRET_KEY`をチャットに貼ってしまったため再生成、`POSTGRES_PASSWORD`の先頭に誤って混入していたコロンを削除して修正済み）。

## 5. 本番向け設定の調整

リポジトリ側（開発機）で以下を変更し、GitHubにpush済み。VPS側では`git pull`で取得する。

### 変更内容

1. **`config/settings.py`**
   - `CSRF_TRUSTED_ORIGINS`を`.env`の`DJANGO_CSRF_TRUSTED_ORIGINS`から読み込むように追加（HTTPS経由のフォーム送信でCSRF検証エラーになるのを防ぐ）
   - `SECURE_PROXY_SSL_HEADER`を追加（nginxがTLSを終端しHTTPでDjangoに中継するため、`X-Forwarded-Proto`ヘッダーを見てHTTPS判定させる）
   - `STATIC_ROOT`を追加（`collectstatic`の出力先。nginxから直接配信する）

2. **`docker-compose.yml`**
   - `db`のポート公開を`5432:5432` → `127.0.0.1:5432:5432`に変更（PostgreSQLをインターネットに直接晒さない）
   - `web`のポート公開を`8000:8000` → `127.0.0.1:8000:8000`に変更（Djangoアプリへの直接アクセスを遮断し、nginx経由のみに限定）

3. **`docker-compose.prod.yml`（新規）**
   - 本番専用の上書き設定。`web`の起動コマンドを開発用の`runserver`（Dockerfileの`CMD`）ではなく`gunicorn`に変更、`restart: always`を設定

### VPS側で実施すること

```bash
cd ~/momotools
git pull
```

`.env`に以下を追記（ドメインは実際に取得したものに合わせる）：

```bash
nano .env
```

```
DJANGO_CSRF_TRUSTED_ORIGINS=https://jkmomo.net,https://www.jkmomo.net
```

本番構成でビルド・起動し、マイグレーション/静的ファイル収集/管理者ユーザー作成を行う：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

以降、本番での起動・再起動は必ず `-f docker-compose.yml -f docker-compose.prod.yml` を付けて実行する（付け忘れると開発用の`runserver`で起動してしまう）。

*(実施待ち：まずリポジトリ側の変更をpushする必要あり)*

## 6. nginx + Let's Encrypt(certbot)でのリバースプロキシ/TLS設定

*(未実施。独自ドメインの有無を要確認)*

## 7. コンテナの起動・自動起動設定

*(未実施)*

## 8. 動作確認

*(未実施)*

## 9. （任意）バックアップ運用

*(未実施)*
