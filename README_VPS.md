# momoTools 本番環境構築手順（VPS / Ubuntu）

VPS上にmomoToolsを本番稼働させるための構築〜初回デプロイ手順を、実施した順に記録する。

## 前提

- VPS: 2コア / 2GB メモリ
- OS: Ubuntu 26.04 LTS (Resolute Raccoon)
- IPアドレス: 133.18.145.216
- SSHユーザー: ubuntu（鍵認証、ポート22）
- ドメイン: jkmomo.net
- 用途: 個人利用・友人公開程度（大量同時アクセスなし）
- 構成: `uv`管理の仮想環境 + systemdサービス + ネイティブPostgreSQL。`nginx`でリバースプロキシ + TLS終端。

## 進捗

- [x] 1. VPSの初期設定
- [x] 2. リポジトリのクローン
- [x] 3. 本番用`.env`の作成
- [x] 4. PostgreSQLのインストールとDB作成
- [x] 5. 本番向け設定の調整・依存関係インストール・マイグレーション
- [x] 6. nginx + Let's Encrypt(certbot)でのリバースプロキシ/TLS設定
- [x] 7. systemdサービスの作成・起動
- [x] 8. 動作確認
- [x] 9. （任意）バックアップ運用

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

## 2. リポジトリのクローン

```bash
git clone https://github.com/momo-muscat/momotools.git
cd momotools
```

結果：クローン成功（`~/momotools`配下に展開）。

## 3. 本番用`.env`の作成

`.env`は`.gitignore`対象のためリポジトリに含まれない。VPS上で新規作成する。

```bash
cd ~/momotools
cp .env.example .env
nano .env
```

以下の値を設定する：

```
DEBUG=False
DJANGO_SECRET_KEY=<新規生成した値に変更>
DJANGO_ALLOWED_HOSTS=jkmomo.net,www.jkmomo.net,133.18.145.216
DJANGO_CSRF_TRUSTED_ORIGINS=https://jkmomo.net,https://www.jkmomo.net
DATABASE_URL=postgres://momotools:<強力なパスワードに変更>@127.0.0.1:5432/momotools

POSTGRES_DB=momotools
POSTGRES_USER=momotools
POSTGRES_PASSWORD=<DATABASE_URLと同じ強力なパスワード>
```

`DJANGO_SECRET_KEY`は使い回さず、本番専用の値を新規生成する。以下のコマンドでランダムな値を生成できる。

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

生成された文字列を`DJANGO_SECRET_KEY`にコピーする。`POSTGRES_PASSWORD`も同様に推測されにくい値に変更し、`DATABASE_URL`内のパスワードと一致させる。

結果：作成・設定完了（`DJANGO_SECRET_KEY`をチャットに貼ってしまったため再生成、`POSTGRES_PASSWORD`の先頭に誤って混入していたコロンを削除して修正済み）。

## 4. PostgreSQLのインストールとDB作成

`README.md`の「Linux環境構築手順 3.」と同じ要領（VPS上のubuntuユーザーで実行）。

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

`.env`で設定したロール名・パスワードでロールとDBを作成する。

```bash
grep POSTGRES_PASSWORD .env   # .envに設定したパスワードを確認

sudo -u postgres psql -c "CREATE ROLE momotools WITH LOGIN PASSWORD '<上で確認したパスワード>';"
sudo -u postgres createdb momotools --owner=momotools

# 疎通確認
psql -h 127.0.0.1 -U momotools -d momotools -c '\conninfo'
```

Djangoアプリ自身はVPS上（同一ホスト）から`127.0.0.1:5432`へTCP接続するのみで、外部に公開する必要はない。`listen_addresses`はデフォルトの`localhost`のままでよく、ufwでも5432番ポートは開放しない。

## 5. 本番向け設定の調整・依存関係インストール・マイグレーション

リポジトリ側（開発機）で以下を変更し、GitHubにpush済み。VPS側では`git pull`で取得する。

### 変更内容（`config/settings.py`）

- `CSRF_TRUSTED_ORIGINS`を`.env`の`DJANGO_CSRF_TRUSTED_ORIGINS`から読み込むように追加（HTTPS経由のフォーム送信でCSRF検証エラーになるのを防ぐ）
- `SECURE_PROXY_SSL_HEADER`を追加（nginxがTLSを終端しHTTPでDjangoに中継するため、`X-Forwarded-Proto`ヘッダーを見てHTTPS判定させる）
- `STATIC_ROOT`を追加（`collectstatic`の出力先。nginxから直接配信する）

### VPS側で実施すること

```bash
cd ~/momotools
git pull

curl -LsSf https://astral.sh/uv/install.sh | sh   # uv未導入なら
uv sync

uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py createsuperuser
```

## 6. nginx + Let's Encrypt(certbot)でのリバースプロキシ/TLS設定

### DNS設定（つまずいた点）

`jkmomo.net`の取得元はお名前.com。DNS反映で以下のトラブルがあった：

1. Aレコードを編集した画面が、実は`dnsv.jp`（別サービス）側のゾーン編集画面だった
2. 一方、ドメインの実際のネームサーバー委任は`dns1/dns2.onamae.com`になっており、`dnsv.jp`側は権威サーバーとして認識されずREFUSEDエラーが発生
3. 誤って「onamae.comのネームサーバーに戻す」対応をしてしまったが、これは逆方向の判断だった
4. 正しい対応：`dnsv.jp`側の編集画面で「レコード情報の登録とあわせてDNSレコード設定用のネームサーバーに変更する」にチェックを入れて保存 → NS委任を`dnsv.jp`側に切り替えることで解決
5. さらにAレコードのVALUE欄で`133.18.45.216`（1桁抜け）という入力ミスもあり、二重に原因があった

最終的に `dig @8.8.8.8 jkmomo.net A` / `dig @8.8.8.8 www.jkmomo.net A` ともに `133.18.145.216` を返すことを確認。

### nginx（VPSホスト側にインストール）

gunicorn（systemdサービス）は`127.0.0.1:8000`にのみバインドしているため、外部からのアクセスはVPSホスト上のnginxが中継する。

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

## 7. systemdサービスの作成・起動

```bash
sudo tee /etc/systemd/system/momotools.service > /dev/null <<'EOF'
[Unit]
Description=momotools gunicorn daemon
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/momotools
EnvironmentFile=/home/ubuntu/momotools/.env
ExecStart=/home/ubuntu/momotools/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now momotools
sudo systemctl status momotools
journalctl -u momotools -n 50 --no-pager
```

> gunicornは`127.0.0.1:8000`に直接バインドする（`0.0.0.0`にしないこと）。nginxのみが到達でき、
> 外部から直接Djangoアプリへアクセスできないようにするため。

結果：

- gunicorn（systemdサービス）起動、`127.0.0.1:8000`限定バインドを確認
- マイグレーション適用済み、`collectstatic`で静的ファイル反映済み
- 管理者ユーザー`admin`（メール: doi@jkmomo.com）を作成済み
- 自動起動：`momotools.service`に`Restart=always`・`WantedBy=multi-user.target`を設定済みのため、VPS再起動時も自動的に起動する

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

開発機側でcommit・push → VPS側で`git pull`→本番デプロイ手順（`README_DEPLOY.md`参照）を実行し、再デプロイ。

結果：`https://jkmomo.net/momotools/`および管理サイト`https://jkmomo.net/momotools/admin/`ともに正常にアクセス・ログインできることを確認。TLS/nginx/Djangoの一連の本番構成が動作していることを確認済み。

## 9. （任意）バックアップ運用

PostgreSQLの日次バックアップを`scripts/backup_db.sh`（リポジトリ管理）で実施する。

### 仕様

- バックアップ先: `~/momo/backup/momotools.sql.gz`
- 実行前に、既存の（前日分の）バックアップを`~/momo/backup/old/momotools_YYYYMMDD.sql.gz`へ日付付きで退避（日付はファイルの更新日時から取得）
- `~/momo/backup/old`内の90日（3ヶ月）超のバックアップは自動削除
- ネイティブPostgreSQLに対して直接`pg_dump`（TCP、`.env`の`POSTGRES_USER`/`POSTGRES_DB`を利用）を実行する

### セットアップ

```bash
cd ~/momotools
git pull
chmod +x scripts/backup_db.sh
./scripts/backup_db.sh   # 動作確認
ls -la ~/momo/backup
```

cronに毎日0時実行として登録：

```bash
(crontab -l 2>/dev/null; echo "0 0 * * * /home/ubuntu/momotools/scripts/backup_db.sh >> /home/ubuntu/momo/backup/backup.log 2>&1") | crontab -
crontab -l
```

結果：手動実行での動作確認、cron登録ともに完了。

### 復元手順

バックアップファイル（`~/momo/backup/momotools.sql.gz`、または過去分の`~/momo/backup/old/momotools_YYYYMMDD.sql.gz`）からDBを復元する場合。

```bash
cd ~/momotools

# 復元したいバックアップファイルを指定
BACKUP_FILE=~/momo/backup/momotools.sql.gz
# 過去の日付分を戻す場合の例: BACKUP_FILE=~/momo/backup/old/momotools_20260601.sql.gz

# アプリを一時停止（復元中の書き込み事故を防ぐ）
sudo systemctl stop momotools

# DBを空の状態に作り直す
sudo -u postgres psql -c "DROP DATABASE IF EXISTS momotools;" -c "CREATE DATABASE momotools OWNER momotools;"

# バックアップを流し込む
gunzip -c "$BACKUP_FILE" | psql -h 127.0.0.1 -U momotools -d momotools

# アプリを再開
sudo systemctl start momotools
```

> `DROP DATABASE`を伴うため、実行前に対象のバックアップファイルと日付を必ず確認すること。誤って本番運用中に無関係な古いバックアップを復元すると、その時点以降のデータが失われる。

---

## トラブルシューティング

### 管理サイトのCSS/アイコンが崩れる（一部PCのみ・404/403）

**症状**：本番の管理サイト（`/momotools/admin/`）で、一部のPCのブラウザだけテーマ切り替えアイコンが黒い四角のまま表示され、本来スクリーンリーダー用に隠れているはずのラベル文言もそのまま見えてしまう。他のPCでは正常に表示される。

**原因**：Djangoの`{% static %}`タグは`STATIC_URL`の値に関わらずルート絶対パス（例：`/static/admin/css/dark_mode.css`）を出力する。nginx側は`location /static/ { alias /home/ubuntu/momotools/staticfiles/; }`でこれに対応しているが、`/home/ubuntu`のパーミッションが`750`（他ユーザーに実行権限なし）だったため、nginxのworkerプロセス（`www-data`）がこのディレクトリを通過できず、`dark_mode.css`等へのリクエストが**誰に対しても**403 Forbiddenになっていた。「一部PCのみ」に見えていたのは、正常だった頃に読み込んだCSSをブラウザがキャッシュして使い回していたPCでは症状が表面化せず、キャッシュを持たないPC（新規アクセス・キャッシュクリア後など）でのみ実際のリクエストが飛んで403が露呈していたため。

**確認方法**：

```bash
namei -l /home/ubuntu/momotools/staticfiles/admin/css/dark_mode.css
```

途中のディレクトリ（`/home/ubuntu`等）の権限に`x`（実行権限）が欠けている行がないか確認する。

**対処**：

```bash
sudo chmod o+x /home/ubuntu
```

読み取り権限（`r`）は付与しないため、`ls ~ubuntu`でホームディレクトリの中身を一覧表示されることはなく、パスを知っているファイルへの到達のみを許可する変更になる。

> **今後の注意点**：「複数プロジェクトの共存方針」に従って新規プロジェクトを追加する際、静的ファイルの配信元を同様に`/home/<user>/`配下に置く場合は、同じ理由で403になりうる。ホームディレクトリの実行権限（`o+x`）を確認するか、そもそも`/var/www/`配下など、ホームディレクトリに依存しない場所に静的ファイルを置く方が本質的には安全（パターンBの`/var/www/staticsite`はこの問題が起きない）。

---

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

## HeidiSQLでのDB接続設定（SSHトンネル経由）

VPS上のPostgreSQLは`127.0.0.1:5432`限定でネイティブインストールされており（ufwも22/80/443しか開放していない）、外部に直接晒していない。WindowsからHeidiSQLで接続する場合は、WinSCPと同じSSH鍵を使ったSSHトンネル経由で接続する。この方法ならVPS側の設定変更（ufw/pg_hba/listen_addresses）は一切不要。

### HeidiSQL側の設定（Windows端末ごと）

新規セッションを作成し、以下を設定する。

**SSHトンネルタブ**

| 項目 | 値 |
|---|---|
| Use SSH tunnel | チェックON |
| SSH executable | `plink.exe`のパス（HeidiSQL同梱、例: `C:\Program Files\HeidiSQL\plink.exe`） |
| SSHホスト+ポート | `133.18.145.216` / `22` |
| ユーザー名 | `ubuntu` |
| 秘密鍵ファイル | WinSCPと同じ秘密鍵（`id_ed25519`等） |
| ローカルポート | 任意の空きポート（例: `3307`） |

> つまずいた点：「SSH executable」と「SSHホスト+ポート」を取り違えて入力すると、接続時に
> "Could not execute SSH command" / "指定されたファイルが見つかりません"というエラーになる
> （Windowsが実行ファイルとして解決しようとした先頭トークンが存在しないため）。前者は
> `plink.exe`本体のパス、後者は接続先VPSのIPアドレスである点に注意。

**設定（メイン）タブ**

| 項目 | 値 |
|---|---|
| Network type | PostgreSQL (libpq) |
| Hostname / IP | `127.0.0.1`（SSHトンネル経由なので、VPS自身から見たlocalhost） |
| Port | `5432` |
| User | `momotools` |
| Password | `.env`の`POSTGRES_PASSWORD`（`DATABASE_URL`内のパスワードと同一） |
| Databases | `momotools` |

初回接続時、Plinkから「Store key in cache?」（ホスト鍵の確認）を聞かれる。表示された
fingerprintを確認の上「はい」でキャッシュに登録すれば、以降は聞かれなくなる。

結果：接続確認済み。

---

## 複数プロジェクトの共存方針（nginx）

`jkmomo.net`配下に今後複数プロジェクトを追加していく想定のため、nginxをパスベースのリバースプロキシ／ルーターとして使い、プロジェクトごとに独立させる方針とする。

### 基本方針

- **1プロジェクト = 1プロセス（systemdサービスまたは静的配信）**として完全に分離する。同一Djangoプロジェクトにアプリを増殖させるのではなく、プロジェクトごとに別ディレクトリ・別systemdサービス・別ポートを持たせる。
- nginxが`server_name jkmomo.net www.jkmomo.net`の1つのserverブロック内で、パスごとに`location`を振り分ける。
- 技術スタック（Django / Flask / Node / 静的HTML等）を問わず同じパターンで追加できる。
- DB（PostgreSQL）はサーバー自体は共有してよいが、**プロジェクトごとに別データベース名**（例: `momotools`, `newproject`）を割り当て、テーブルは分離する。

### パターンA: アプリケーション（プロセス）を追加する場合

1. 今回の`momotools`と同じ要領で新規プロジェクトを作成する（`uv init` → 依存追加 → systemdユニット作成）。
2. systemdユニットの`ExecStart`で、他プロジェクトと衝突しない内部ポートを`127.0.0.1`限定でバインドする（例: `127.0.0.1:8001`）。
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

ファイルをVPS上のディレクトリに置いてnginxから直接配信する。

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
| `/momotools/` | momotools（Django, gunicorn） | 127.0.0.1:8000（systemdサービス） |

新規プロジェクトを追加するたびに、このテーブルへ追記していく。
