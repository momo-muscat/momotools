# momoTools 本番環境構築手順（VPS / Ubuntu）

VPS上にmomoToolsを本番稼働させるための構築〜初回デプロイ手順を、実施した順に記録する。

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
- [x] 5. 本番向け設定の調整（DEBUG, ALLOWED_HOSTS, gunicorn化など）
- [x] 6. nginx + Let's Encrypt(certbot)でのリバースプロキシ/TLS設定
- [x] 7. コンテナの起動・自動起動設定
- [ ] 8. 動作確認（`urls.py`修正のcommit・push・再デプロイ待ち）
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

### DNS設定（つまずいた点）

`jkmomo.net`の取得元はお名前.com。DNS反映で以下のトラブルがあった：

1. Aレコードを編集した画面が、実は`dnsv.jp`（別サービス）側のゾーン編集画面だった
2. 一方、ドメインの実際のネームサーバー委任は`dns1/dns2.onamae.com`になっており、`dnsv.jp`側は権威サーバーとして認識されずREFUSEDエラーが発生
3. 誤って「onamae.comのネームサーバーに戻す」対応をしてしまったが、これは逆方向の判断だった
4. 正しい対応：`dnsv.jp`側の編集画面で「レコード情報の登録とあわせてDNSレコード設定用のネームサーバーに変更する」にチェックを入れて保存 → NS委任を`dnsv.jp`側に切り替えることで解決
5. さらにAレコードのVALUE欄で`133.18.45.216`（1桁抜け）という入力ミスもあり、二重に原因があった

最終的に `dig @8.8.8.8 jkmomo.net A` / `dig @8.8.8.8 www.jkmomo.net A` ともに `133.18.145.216` を返すことを確認。

### nginx（VPSホスト側にインストール、Dockerコンテナ化しない）

Django(`web`)コンテナは`docker-compose.yml`で`127.0.0.1:8000`にのみポート公開しているため、外部からのアクセスはVPSホスト上のnginxが中継する。

`momotools`用のリバースプロキシ設定を作成し、有効化する。

```bash
sudo tee /etc/nginx/sites-available/momotools > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name jkmomo.net www.jkmomo.net;

    location /static/ {
        alias /home/ubuntu/momotools/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/momotools /etc/nginx/sites-enabled/momotools
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

> つまずいた点：初回実行時、コマンドを表示用の`cat <<'EOF' ... EOF`ラッパーごとターミナルに貼り付けてしまい、実際には何も実行されていなかった（`cat`が中身をそのまま画面に表示しただけ）。この状態に気づかず次のcertbot実行に進んだため、証明書が意図した`sites-available/momotools`ではなく、nginxの初期設定（`sites-available/default`）に対して発行されてしまった。`sites-enabled/default`のシンボリックリンクを削除し、`momotools`設定を改めて作成・有効化することで解消（`nginx -t`で"conflicting server name"警告が出ないことを確認）。

### Let's Encrypt(certbot)でのTLS証明書取得

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d jkmomo.net -d www.jkmomo.net --redirect -m doi@jkmomo.com --agree-tos --no-eff-email
sudo nginx -t
sudo certbot renew --dry-run
```

結果：証明書発行成功。

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/jkmomo.net/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/jkmomo.net/privkey.pem
This certificate expires on 2026-10-22.
```

`certbot.timer`（systemd）による自動更新が設定済み。`certbot renew --dry-run`もシミュレーション成功を確認済み。

`sites-enabled/`には`momotools`のみが有効な状態（`default`は削除済み）で、`nginx -t`もconflicting server name警告なしでpass。

## 7. コンテナの起動・自動起動設定

```bash
cd ~/momotools
git pull
```

`.env`に本番用のCSRF設定を追記：

```
DJANGO_CSRF_TRUSTED_ORIGINS=https://jkmomo.net,https://www.jkmomo.net
```

本番構成（`docker-compose.yml` + `docker-compose.prod.yml`）でビルド・起動し、マイグレーション/静的ファイル収集/管理者ユーザー作成を実施：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py createsuperuser
```

結果：

- `web`（gunicorn）/ `db`ともに起動、`127.0.0.1`限定バインドを確認（`docker compose ps`でPORTSが`127.0.0.1:8000->8000/tcp`等になっていることを確認）
- マイグレーション適用済み、`collectstatic`で静的ファイル反映済み
- 管理者ユーザー`admin`（メール: doi@jkmomo.com）を作成済み
- 自動起動：`docker-compose.prod.yml`で`web`/`db`双方に`restart: always`を設定済み。Docker Engine自体もsystemdサービスとして有効化済み（`enabled`）のため、VPS再起動時もコンテナは自動的に起動する。

## 8. 動作確認

`https://jkmomo.net/`にアクセスしたところ、Django標準の404「Not Found」が返った。

原因調査の結果、`config/urls.py`で`top_page`アプリが`/momotools/`配下にマウントされており（ルート`/`にはビュー未割り当て）、さらに管理サイト（`admin.site.urls`）もコメントアウトで無効化されていたことが判明。

このプロジェクトは`https://jkmomo.net/momotools/`以下を専有し、他プロジェクトを`/xxxx/`として追加していく方針のため、`urls.py`を以下のように修正（詳細は本ファイル末尾「複数プロジェクトの共存方針」を参照）。

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("momotools/admin/", admin.site.urls),
    path("momotools/", include("top_page.urls")),
]
```

*(実施待ち：開発機側でこの変更をcommit・pushし、VPS側で`git pull`→本番デプロイ手順（本ファイル該当セクション参照）を実行後、`https://jkmomo.net/momotools/`と`https://jkmomo.net/momotools/admin/`で最終確認を行う)*

## 9. （任意）バックアップ運用

*(未実施)*

---

# momoTools 本番デプロイ手順

環境構築（上記）完了後、コードの変更を本番に反映する際の日々の更新手順。

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

## WinSCPでのファイルアクセス設定

VPS上のファイルをWindowsからGUIで閲覧・編集できるよう、`ubuntu`ユーザーでWinSCP接続できるようにした。

### VPS側の設定（1回のみ）

`/etc/nginx/`等のroot所有ファイルもWinSCPから編集できるよう、`sftp-server`をsudo経由で起動する権限だけを限定的に許可する（`ubuntu`ユーザーの一般的なsudo権限自体は変更しない）。

```bash
which sftp-server 2>/dev/null; dpkg -L openssh-sftp-server | grep sftp-server
# → /usr/lib/openssh/sftp-server であることを確認

echo "ubuntu ALL=(root) NOPASSWD: /usr/lib/openssh/sftp-server" | sudo tee /etc/sudoers.d/winscp-sftp-root
sudo chmod 440 /etc/sudoers.d/winscp-sftp-root
sudo visudo -c
```

> **注意**: `ubuntu`ユーザーは元々無制限sudoを持っているため実害の増分は小さいが、この設定により「パスワードなしでrootとしてファイル読み書き」が可能になる点は認識しておく。

結果：設定完了、`visudo -c`で構文エラーなしを確認済み。

### WinSCP側の設定（Windows端末ごと）

普段のSSH接続に使っている秘密鍵（`id_ed25519`等）を使用する。WinSCP 5.15以降はOpenSSH形式の鍵をそのまま読み込める。

**① 通常セッション（プロジェクトファイル用）**

- File protocol: `SFTP`
- Host name: `133.18.145.216` / Port: `22` / User name: `ubuntu`
- Advanced → SSH → Authentication → Private key file に秘密鍵を指定

**② root相当アクセス用セッション（`/etc/nginx/`等の編集用）**

①を複製し、Advanced → Environment → SFTP タブの「SFTP server」欄に以下を設定する。

```
sudo /usr/lib/openssh/sftp-server
```

これで接続するとルート（`/`）配下すべてに読み書きできる。普段は①を使い、管理者権限が必要な作業のときのみ②を使う。

結果：接続確認済み。

---

## 複数プロジェクトの共存方針（nginx）

`jkmomo.net`配下に今後複数プロジェクトを追加していく想定のため、nginxをパスベースのリバースプロキシ／ルーターとして使い、プロジェクトごとに独立させる方針とする。

### 基本方針

- **1プロジェクト = 1コンテナ（または非コンテナの静的配信）**として完全に分離する。同一Djangoプロジェクトにアプリを増殖させるのではなく、プロジェクトごとに別ディレクトリ・別`docker-compose.yml`・別ポートを持たせる。
- nginxが`server_name jkmomo.net www.jkmomo.net`の1つのserverブロック内で、パスごとに`location`を振り分ける。
- 技術スタック（Django / Flask / Node / 静的HTML等）を問わず同じパターンで追加できる。
- DB（PostgreSQL）はサーバー自体は共有してよいが、**プロジェクトごとに別データベース名**（例: `momotools`, `newproject`）を割り当て、テーブルは分離する。

### パターンA: アプリケーション（コンテナ）を追加する場合

1. 今回の`momotools`と同じ要領で新規プロジェクトを作成する（`uv init` → 依存追加 → `Dockerfile` / `docker-compose.yml`作成）。
2. `docker-compose.yml`の`ports`は他プロジェクトと衝突しない内部ポートを`127.0.0.1`限定で公開する（例: `127.0.0.1:8001:8000`）。
3. nginxの設定に`location`を追記する。

```nginx
location /newproject/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

4. `sudo nginx -t && sudo systemctl reload nginx`で反映。

### パターンB: 静的HTMLを直接置く場合

コンテナ化せず、ファイルをVPS上のディレクトリに置いてnginxから直接配信する。

```bash
sudo mkdir -p /var/www/staticsite
scp -r ./dist/* ubuntu@133.18.145.216:/tmp/staticsite/
ssh ubuntu@133.18.145.216 "sudo cp -r /tmp/staticsite/* /var/www/staticsite/"
```

```nginx
location /staticsite/ {
    alias /var/www/staticsite/;
    index index.html;
}
```

### 現在の割り当て

| パス | 内容 | ポート/配信元 |
|---|---|---|
| `/momotools/` | momotools（Django, gunicorn） | 127.0.0.1:8000（コンテナ） |

新規プロジェクトを追加するたびに、このテーブルへ追記していく。
