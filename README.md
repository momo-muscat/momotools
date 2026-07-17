# momoToolsプロジェクトの構築
## 環境
1. WSL2(Ubuntu 26.04 LTS) user:momo, pwd:5150
1. Docker Engine
1. Python
1. uv
1. Django
1. PostgreSQL
1. Dev Containers
1. GitHub（レポジトリ未作成）

追加コンポーネント（2〜6以外に必須として導入したもの）
1. Docker Compose (v2 plugin) — Django/PostgreSQLの複数コンテナ連携に使用
1. django-environ — `.env`による秘密情報・DB接続情報の管理
1. .devcontainer/devcontainer.json — VS Code Dev Containersでのコンテナアタッチ設定
1. .gitignore — `.env`, `db.sqlite3` 等の除外設定
1. postgresql-client相当（psql） — `postgres:16-alpine`イメージに同梱、`docker compose exec db psql ...`で利用
1. pre-commit + ruff/black — コード品質チェック

## TODO
- ~~上記2～6のコンポーネント以外に必須なものはあれば提案してほしい~~ 完了（上記「追加コンポーネント」参照）
- ~~OKであればコンポーネントをDocker Engine上で動作するようインストール~~ 完了
- ~~インストールしたときの手順（コマンド）を下記のLinux環境構築手順に記入~~ 完了

## Linux環境構築手順

### 1. Docker Engineのインストール（要sudo）
公式リポジトリからDocker Engine + Compose pluginを導入する。

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

# sudoなしでdockerを使えるようにする（要WSL再起動でグループ反映）
sudo usermod -aG docker $USER

# WSL2 + systemd環境ではサービスとして起動
sudo service docker start
```

> **注意（WSL2特有の落とし穴）**: `usermod -aG docker $USER` の反映には、ターミナルを開き直すだけでは不十分な場合がある（systemdのユーザーセッションが再利用されるため）。反映されない場合は Windows側で `wsl --shutdown` を実行しWSLを完全再起動するか、それまでは `sudo docker ...` で実行する。

### 2. uvのインストール（sudo不要）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Djangoプロジェクトの作成（uv管理）

```bash
uv init --no-readme --python 3.12
rm -f main.py
uv add django "psycopg[binary]" django-environ gunicorn
uv add --dev ruff black pre-commit
uv run django-admin startproject config .
```

`config/settings.py` は `django-environ` 経由で `.env` から `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` / `DATABASE_URL` を読み込むように変更済み。`.env.example` を `.env` にコピーし、値を環境に合わせて調整する。

### 4. コンテナのビルドと起動

`Dockerfile`（Python 3.12-slim + uv）と `docker-compose.yml`（web=Django, db=PostgreSQL16）を用意済み。

```bash
sudo docker compose up --build -d
sudo docker compose exec web python manage.py migrate
sudo docker compose ps
```

`docker`グループが反映されていれば `sudo` は不要。

### 5. Dev Containersでの開発

VS Codeで `.devcontainer/devcontainer.json` を検出させ、「Reopen in Container」を実行すると `web` サービスにアタッチされる（`postCreateCommand` で `uv sync` 実行）。

### 6. コード品質チェック

```bash
uv run ruff check .
uv run black --check .
uv run pre-commit install   # git commit時に自動実行させる場合
```

## Django操作コマンド

### サーバ起動

`web`コンテナはDockerfileの`CMD`で起動時に`runserver`を自動実行しているため、Dev Containerのターミナルで改めて起動する必要はない（`That port is already in use.`になる）。コード変更はオートリロードで反映される。

```bash
uv run python manage.py runserver 0.0.0.0:8000
```

別ポートで起動すれば、既存のサーバ（PID 1）と並行して利用できる。ホストから見るにはVS Codeの「PORTS」パネルで該当ポートを追加転送する必要がある。

```bash
uv run python manage.py runserver 0.0.0.0:8001
```

> **`0.0.0.0:`の有無について**: 明示すると全ネットワークインターフェースで待ち受け、Dockerの`ports`マッピングや同一Dockerネットワーク上の他コンテナからも到達できる。省略時のデフォルト`127.0.0.1`はループバックのみで、Dockerの通常のポートマッピング経由では外から届かない（VS CodeのPORTSパネル転送はコンテナ内部からループバックへ直接繋ぐ特殊な経路のため例外的に動く）。用途を問わないなら`0.0.0.0`指定が無難。

### マイグレーション

```bash
uv run python manage.py migrate
``

### アプリ作成

```bash
uv run python manage.py startapp <app名>
```

# 別PCでの環境構築手順

このプロジェクトはGitHub（https://github.com/momo-muscat/momotools.git）で管理しているため、別PCで編集する場合は上記「Linux環境構築手順」の3.（`uv init`や`startproject`によるDjangoプロジェクトの雛形作成）は不要。以下の手順のみでよい。

### 1. WSL2(Ubuntu)の準備
Windows側で未導入の場合は`wsl --install`等でセットアップしておく。

### 2. Docker Engineのインストール
上記「Linux環境構築手順」1.と同じ手順（`docker-ce` / `docker-compose-plugin`導入、`usermod -aG docker $USER`）を実施する。

### 3. uvのインストール
上記「Linux環境構築手順」2.と同じ。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4. リポジトリのクローン

```bash
git clone https://github.com/momo-muscat/momotools.git
cd momotools
```

### 5. `.env`の作成

`.env`は`.gitignore`対象のためリポジトリに含まれない。`.env.example`をコピーして値を環境に合わせて調整する。

```bash
cp .env.example .env
```

> `DJANGO_SECRET_KEY`は本番運用する場合、PCごと・環境ごとに固有の値へ変更することを推奨。

### 6. コンテナのビルドと起動

上記「Linux環境構築手順」4.と同じ。

```bash
sudo docker compose up --build -d
sudo docker compose exec web python manage.py migrate
sudo docker compose ps
```

`docker`グループが反映されていれば`sudo`は不要。

### 7. Dev Containersでの開発

VS Codeで`.devcontainer/devcontainer.json`を検出させ、「Reopen in Container」を実行する。`postCreateCommand`で`uv sync`が自動実行され、依存関係（`uv.lock`基準）が`web`コンテナ内に構築される。

### 8. （任意）コード品質チェックツールの有効化

```bash
uv run pre-commit install   # git commit時に自動実行させる場合
```
