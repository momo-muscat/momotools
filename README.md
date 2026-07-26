# momoToolsプロジェクトの構築
## 環境
1. WSL2(Ubuntu 26.04 LTS) user:momo, pwd:5150
1. Python
1. uv
1. Django
1. PostgreSQL（ネイティブインストール）
1. GitHub（レポジトリ未作成）

追加コンポーネント（2〜5以外に必須として導入したもの）
1. django-environ — `.env`による秘密情報・DB接続情報の管理
1. .gitignore — `.env`, `db.sqlite3` 等の除外設定
1. pre-commit + ruff/black — コード品質チェック

> **旧構成からの変更点**: 以前はDocker Engine/Docker Compose/Dev Containersを使ってDjango+PostgreSQLを
> コンテナ化していたが、コンテナのデフォルト実行ユーザーがrootだったことによる所有権の破壊（`git commit`不能）や、
> Claude Codeのセッション状態がリビルドの度に消えるなど、環境構築の手間が繰り返し問題になったため撤去した。
> 現在はPython(uv管理の仮想環境)・PostgreSQLとも素のWSL2上にネイティブインストールする構成。

## Linux環境構築手順

### 1. uvのインストール（sudo不要）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. PostgreSQLのインストール（要sudo）

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
psql --version
```

ロールとDBを作成する。ロール名はOSユーザー名と一致させることで、Unixソケット経由の
peer認証（パスワード不要）で接続できる。

```bash
sudo -u postgres createuser --createdb momo
sudo -u postgres createdb momotools --owner=momo

# パスワード無しで繋がることを確認
psql -d momotools -c '\conninfo'
```

> Ubuntuのデフォルト`pg_hba.conf`には`local all all peer`が入っているため、通常は追加設定不要。
> 繋がらない場合は`sudo cat /etc/postgresql/*/main/pg_hba.conf`で確認し、変更したら
> `sudo systemctl reload postgresql`。

### 3. Djangoプロジェクトの作成（uv管理）

```bash
uv init --no-readme --python 3.12
rm -f main.py
uv add django "psycopg[binary]" django-environ gunicorn
uv add --dev ruff black pre-commit
uv run django-admin startproject config .
```

`config/settings.py` は `django-environ` 経由で `.env` から `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` /
`DATABASE_URL` を読み込むように変更済み。`.env.example` を `.env` にコピーし、値を環境に合わせて調整する。

### 4. 依存関係のインストールとマイグレーション

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser   # 任意
```

### 5. コード品質チェック

```bash
uv run ruff check .
uv run black --check .
uv run pre-commit install   # git commit時に自動実行させる場合
```

## Django操作コマンド

### サーバ起動

```bash
uv run python manage.py runserver 0.0.0.0:8000
```

VS Codeで開発する場合は「WSL」拡張機能でWSL2フォルダを直接開く（Dev Containers不使用）。

### マイグレーション

```bash
uv run python manage.py migrate
```

### アプリ作成

```bash
uv run python manage.py startapp <app名>
```


# 別PCでの環境構築手順

このプロジェクトはGitHub（https://github.com/momo-muscat/momotools.git）で管理しているため、別PCで編集する場合は上記「Linux環境構築手順」の3.（`uv init`や`startproject`によるDjangoプロジェクトの雛形作成）は不要。以下の手順のみでよい。

### 1. WSL2(Ubuntu)の準備
Windows側で未導入の場合は`wsl --install`等でセットアップしておく。

### 2. uvのインストール
上記「Linux環境構築手順」1.と同じ。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. PostgreSQLのインストール
上記「Linux環境構築手順」2.と同じ手順（ネイティブインストール、ロール名はそのPCのOSユーザー名に合わせる）。

### 4. リポジトリのクローン

```bash
git clone https://github.com/momo-muscat/momotools.git
cd momotools
```

### 5. `.env`の作成

`.env`は`.gitignore`対象のためリポジトリに含まれない。`.env.example`をコピーして値を環境に合わせて調整する。
`DATABASE_URL`のロール名部分は、そのPCで作成したOSユーザー名（peer認証のロール名）に置き換えること。

```bash
cp .env.example .env
```

> `DJANGO_SECRET_KEY`は本番運用する場合、PCごと・環境ごとに固有の値へ変更することを推奨。

### 6. 依存関係のインストールとマイグレーション

上記「Linux環境構築手順」4.と同じ。

```bash
uv sync
uv run python manage.py migrate
```

### 7. （任意）コード品質チェックツールの有効化

```bash
uv run pre-commit install   # git commit時に自動実行させる場合
```
