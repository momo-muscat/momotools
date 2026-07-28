# CLAUDE.md

このファイルは、このリポジトリでコードを扱う際にClaude Code（claude.ai/code）へガイダンスを提供する。

## プロジェクト概要

momotoolsは個人利用のDjangoプロジェクト（Django + PostgreSQL、本番はnginxリバースプロキシ）。
`https://jkmomo.net/momotools/`にデプロイされており、同じVPS/ドメインを共有する複数プロジェクトの
うちの1つ（後述の「複数プロジェクトのホスティング」を参照）。日本語で書かれている。README.md、
README_DEPLOY.md、README_VPS.mdに構築・デプロイ・VPSの経緯が日本語で詳しく書かれており、ここに
記載のないインフラ関連事項についてはそれらが正となる。

依存関係は`uv`で管理している（pip/poetryを直接は使わない）。ロックファイルは`uv.lock`。開発・本番
とも、ネイティブインストールしたPostgreSQLに対してホスト上で直接動く（ローカルはWSL2、本番はVPS上の
systemdサービス）。

## コマンド

```bash
# 開発サーバー起動
uv run python manage.py runserver 0.0.0.0:8000

# マイグレーション
uv run python manage.py makemigrations
uv run python manage.py migrate

# アプリ作成（アプリはプロジェクトルート直下ではなくapp/配下に置く構成。手順の詳細
# （apps.pyのname、INSTALLED_APPS/urls.pyの修正が必要な点を含む）はREADME.md参照）
uv run python manage.py startapp <app_name> app/<app_name>

# テスト（アプリごとのtests.py、標準のDjangoテストランナー）
uv run python manage.py test
uv run python manage.py test app.top_page
uv run python manage.py test app.top_page.tests.SomeTestCase.test_some_method  # 単一テスト

# Lint / フォーマット
uv run ruff check .
uv run black --check .
uv run pre-commit install   # 初回のみ。commit時にruff+blackを自動実行させる
```

本番デプロイ（VPS、SSH経由 — 完全な手順はREADME_DEPLOY.md参照）:

```bash
git pull
uv sync
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
sudo systemctl restart momotools
```

## アーキテクチャ

- 単一のDjangoプロジェクト`config/`があり、機能領域ごとに1アプリを`app/`配下にまとめている
  （例: `app/top_page/`）。現状は`top_page`のみ存在（プレースホルダーのランディングページ —
  `top_page/index.html`をレンダリングする`TemplateView`のみで、モデルはまだ無い）。
  `INSTALLED_APPS`やimportではドット区切りのパス`app.top_page`を使うが、Djangoのアプリラベル
  （`manage.py test`やマイグレーション等で使われるもの）は最後の要素である`top_page`のまま。
- **URLはルートにマウントされていない。** `config/urls.py`はすべてを`/momotools/`配下にマウント
  している（管理サイトは`momotools/admin/`、`app.top_page.urls`は`momotools/`）。これは意図的な
  構成で、VPSはnginxのパスベースルーティングによって同一ドメイン上で複数の無関係なプロジェクトを
  ホストしているため、本プロジェクトは`/momotools/`というパスセグメントを占有している。新規に
  アプリ／ビューを追加する際は、ルートマウントされたルートを前提にせず、このプロジェクトのURL
  名前空間の配下に置くこと。
- 設定（`config/settings.py`）は`django-environ`経由で`.env`（gitignore対象。`.env.example`から
  コピーする）から読み込む環境駆動の構成。主な環境変数: `DEBUG`、`DJANGO_SECRET_KEY`、
  `DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`DATABASE_URL`。`LANGUAGE_CODE`は`ja`、
  `TIME_ZONE`は`Asia/Tokyo`。
- **データベース認証はローカルと本番で意図的に異なる。** ローカルではUnixソケット経由のpeer認証で
  PostgreSQLに接続する — Postgresのロール名はOSユーザー名と一致させる必要がある（例:
  `postgres://momo@//var/run/postgresql/momotools`）ため、ローカルで管理すべきパスワードは無い。
  本番ではTCP＋パスワード認証（`postgres://user:pass@127.0.0.1:5432/dbname`）で、アプリが
  systemd経由の固定サービスユーザー（`ubuntu`）で動くため。`.env`内の`POSTGRES_DB`/
  `POSTGRES_USER`/`POSTGRES_PASSWORD`はVPS上の`scripts/backup_db.sh`（`pg_dump`用のTCP認証）
  のみが使用し、Django自体は使用しない。
- `SECURE_PROXY_SSL_HEADER`を設定しているのは、nginxがTLSを終端しDjangoへは平文HTTPでプロキシ
  するため — DjangoはHTTPS判定に`X-Forwarded-Proto`を信頼する。nginx側の設定も合わせて見直す
  こと無しにこれを外さないこと。
- 本番ではgunicorn（`config.wsgi:application`）がsystemdサービス（`momotools.service`）として
  `127.0.0.1:8000`にバインドして動作し、nginxのみがそれと通信する。ローカルでは`manage.py
  runserver`を直接使用しており、開発用のプロセスマネージャーは不要。
- テンプレートはCDNの`<script>`タグ経由でTailwindを使用（ビルドパイプライン無し） —
  現状のパターンは`app/top_page/templates/top_page/index.html`を参照。並行してJinja2バックエンドも
  設定済み（`config/jinja2.py`）で、現状アプリが1つしかないためアプリ単位ではなくプロジェクト直下の
  `jinja2/`ディレクトリを起点にしている — 詳細はREADME.md参照。
- `scripts/backup_db.sh`は、ネイティブのPostgresインスタンスに対して直接`pg_dump`（TCP、
  認証情報は`.env`から）を実行し毎日PostgreSQLのバックアップを取る。古いダンプは`~/momo/backup/old/`
  へローテーションし90日間保持する。VPS上でcron登録されており、リポジトリ内では管理していない。

## 複数プロジェクトのホスティング（VPS）

このアプリは、1つのVPS/nginx/ドメインを共有する可能性のある複数プロジェクトのうちの1つ。
（README_VPS.mdに詳細が記載されている）規約は次の通り: 1プロジェクト＝1プロセス（systemdサービス
または静的ディレクトリ）が`127.0.0.1`にバインドされた自身専用の内部ポートを持ち、nginxが
`location /project-name/`をそこへルーティングする。同じネイティブPostgresサーバーを共有していても、
新規プロジェクトごとに専用のPostgresデータベース（および通常は専用ロール）を持つ。本プロジェクトが
公開ポートにバインドしたりドメインルートを占有したりできる、と想定しないこと。
