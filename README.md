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
1. jinja2 — テンプレートエンジン

## Linux環境構築手順

### 1. WSLのインストール（Windows側、要管理者権限）

ディストリビューションは Ubuntu-26.04 を使用する。PowerShell（管理者）で以下を実行。

```powershell
wsl --install -d Ubuntu-26.04
```

インストール後、再起動を求められたら再起動する。初回起動時にUbuntu側のユーザー名・パスワードを設定する
（本プロジェクトでは user:momo, pwd:5150）。

> 既にWSL自体（別ディストリビューション等）を導入済みで、Ubuntu-26.04のみ追加したい場合は
> `wsl --install -d Ubuntu-26.04`のみでよい（`wsl --install`単体はWSL機能自体の有効化も行う）。
> 導入済みディストリビューション一覧は`wsl -l -v`で確認できる。

### 2. uvのインストール（sudo不要）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. PostgreSQLのインストール（要sudo）

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

#### HeidiSQLなど、Windows側のGUIツールから接続する場合

Django自体はUnixソケット経由のpeer認証で繋がるが、HeidiSQLはWindows側で動くため、Unixソケットは使えず
TCP＋パスワード認証での接続が必要になる。

1. ロールにパスワードを設定する。

    ```bash
    sudo -u postgres psql -c "ALTER ROLE momo WITH PASSWORD 'ここに任意のパスワード';"
    ```

2. `listen_addresses`を全インターフェース待受けに変更する（`/etc/postgresql/18/main/postgresql.conf`）。
   手動でファイルを編集してもよいし、以下のように`sed`で書き換えてもよい。

    ```
    listen_addresses = '*'
    ```

    ```bash
    sudo sed -i "s/^#\?listen_addresses = .*/listen_addresses = '*'/" /etc/postgresql/18/main/postgresql.conf
    grep listen_addresses /etc/postgresql/18/main/postgresql.conf   # '*'になっていることを確認
    ```

    デフォルトの`localhost`のままだとループバック(127.0.0.1)以外からの接続を受け付けず、Windows側の
    GUIツールからは`Connection refused`になる。

3. `pg_hba.conf`（`/etc/postgresql/18/main/pg_hba.conf`）にWSL2のサブネットからの接続を許可する行を追加する。
   手動編集でもよいし、以下のように末尾に追記してもよい。

    ```
    host    momotools       momo            172.25.32.0/20          scram-sha-256
    ```

    ```bash
    echo "host    momotools       momo            172.25.32.0/20          scram-sha-256" | sudo tee -a /etc/postgresql/18/main/pg_hba.conf
    ```

    WSL2のサブネットは`ip addr show eth0`や`hostname -I`で確認できる（環境により異なる。上記の
    `172.25.32.0/20`は例であり、実際の値に置き換えること）。Windowsから
    TCP接続すると送信元IPは`127.0.0.1`ではなくこのサブネット内のアドレスになるため、`127.0.0.1/32`向けの
    デフォルトルールだけでは通らない。

4. 設定を反映する。`listen_addresses`の変更は`reload`では反映されないため`restart`が必要。

    ```bash
    sudo systemctl restart postgresql@18-main
    ss -tln | grep 5432   # 0.0.0.0:5432 でLISTENしていればOK（127.0.0.1のみならlisten_addresses未反映）
    ```

    > WindowsのGUIツールを試す前に、WSL2内から`psql "postgresql://momo@127.0.0.1:5432/momotools"`で
    > TCP＋パスワード接続できるか確認しておくと、パスワード起因の問題とネットワーク起因の問題を切り分けやすい。

5. HeidiSQL（Windows側）の接続設定。

    | 項目 | 値 |
    |---|---|
    | Network type | PostgreSQL (libpq) |
    | Hostname / IP | WSL2のeth0アドレス（`hostname -I`の1つ目の値） |
    | Port | `.env`の`DATABASE_URL`に合わせる（標準構成では`5432`） |
    | User | `momo`（**要注意**: 新規接続作成時のデフォルト値`postgres`のままだと、`pg_hba.conf`に
    `postgres`ロール向けの許可行が無いため`no pg_hba.conf entry for host ..., user "postgres"`で
    接続失敗する。3.で許可したロール名＝`momo`に必ず変更すること） |
    | Password | 手順1で設定したパスワード |
    | Databases | `momotools` |

    > WSL2のIPは再起動のたびに変わりうるため、繋がらなくなったら`hostname -I`で再確認する。毎回確認するのが
    > 面倒な場合はWindows側の`%UserProfile%\.wslconfig`に`networkingMode=mirrored`を追記して
    > `wsl --shutdown`後に再起動すると、`127.0.0.1`固定で接続できる（Windows 11 22H2以降）。

### 4. Djangoプロジェクトの作成（uv管理）

```bash
uv init --no-readme --python 3.12
rm -f main.py
uv add django "psycopg[binary]" django-environ gunicorn
uv add --dev ruff black pre-commit
uv run django-admin startproject config .
```

`config/settings.py` は `django-environ` 経由で `.env` から `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` /
`DATABASE_URL` を読み込むように変更済み。`.env.example` を `.env` にコピーし、値を環境に合わせて調整する。

### 5. 依存関係のインストールとマイグレーション

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser   # 任意
```

### 6. コード品質チェック

```bash
uv run ruff check .
uv run black --check .
uv run pre-commit install   # git commit時に自動実行させる場合
```

## Django関連ライブラリインストール

### jinja2のインストール（テンプレートエンジン）

```bash
uv add jinja2
```

`config/settings.py`の`TEMPLATES`に、既存の`DjangoTemplates`と並べてJinja2バックエンドを追加済み。
DjangoTemplatesは各アプリの`templates/`配下を見る（`APP_DIRS: True`）のに対し、Jinja2側は
プロジェクトルート直下の`jinja2/`ディレクトリ1箇所のみを見る構成にしている（`DIRS`指定・`APP_DIRS: False`）。

```python
{
    "BACKEND": "django.template.backends.jinja2.Jinja2",
    "DIRS": [BASE_DIR / "jinja2"],
    "APP_DIRS": False,
    "OPTIONS": {
        "environment": "config.jinja2.environment",
    },
},
```

`config/jinja2.py`にJinja2の`Environment`を生成する関数を定義し、`static()` / `url()`
（Django標準の`{% static %}`タグ・`reverse()`相当）をテンプレートのグローバル関数として登録している。
Jinja2でテンプレートを書く場合は、`DjangoTemplates`の`<app>/templates/<app名>/`と同じ命名慣習に合わせて
`jinja2/<app名>/foo.html`に配置する（例: `jinja2/top_page/foo.html`）。名前空間はディレクトリ分けのみで
行っており、`DIRS`自体はルート直下の`jinja2/`1箇所のまま。

## Django操作コマンド

### サーバ起動

```bash
uv run python manage.py runserver 0.0.0.0:8000
uv run python manage.py runserver 127.0.0.1:8000
uv run python manage.py runserver 8000
uv run python manage.py runserver
```

VS Codeで開発する場合は「WSL」拡張機能でWSL2フォルダを直接開く（Dev Containers不使用）。

### マイグレーション

```bash
uv run python manage.py migrate
```

### アプリ作成

アプリは`apps/`配下にまとめる構成のため、`startapp`をそのまま実行するとルート直下に作られてしまう点に注意。
`--directory`で出力先を指定し、生成後に`apps.py`の`name`を`apps.<app名>`へ修正する。

```bash
mkdir -p apps/<app名>
uv run python manage.py startapp <app名> apps/<app名>
```

生成された`apps/<app名>/apps.py`の`name = "<app名>"`を`name = "apps.<app名>"`に変更し、
`config/settings.py`の`INSTALLED_APPS`と`config/urls.py`の`include()`にも`apps.<app名>`で追記する
（`apps/top_page`が実例）。


# 別PCでの環境構築手順

このプロジェクトはGitHub（https://github.com/momo-muscat/momotools.git）で管理しているため、別PCで編集する場合は上記「Linux環境構築手順」の4.（`uv init`や`startproject`によるDjangoプロジェクトの雛形作成）は不要。以下の手順のみでよい。

### 1. WSL2(Ubuntu)の準備
上記「Linux環境構築手順」1.と同じ。Windows側で未導入の場合は`wsl --install -d Ubuntu-26.04`でセットアップしておく。

### 2. uvのインストール
上記「Linux環境構築手順」2.と同じ。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. PostgreSQLのインストール
上記「Linux環境構築手順」3.と同じ手順（ネイティブインストール、ロール名はそのPCのOSユーザー名に合わせる）。

### 4. リポジトリのクローン

```bash
git clone https://github.com/momo-muscat/momotools.git
cd momotools
```

> クローン先の`momotools`ディレクトリが何らかの理由で事前に存在し、かつ所有者がroot等
> 自ユーザー以外になっている場合、`git clone`が書き込み権限エラーで失敗する。
> その場合は先に所有権を戻してからクローンする。
>
> ```bash
> sudo chown -R <OSユーザー名>:<OSユーザー名> momotools
> ```

### 5. `.env`の作成

`.env`は`.gitignore`対象のためリポジトリに含まれない。`.env.example`をコピーして値を環境に合わせて調整する。
`DATABASE_URL`のロール名部分は、そのPCで作成したOSユーザー名（peer認証のロール名）に置き換えること。

```bash
cp .env.example .env
```

> `DJANGO_SECRET_KEY`は本番運用する場合、PCごと・環境ごとに固有の値へ変更することを推奨。

> `.env.example`の`DATABASE_URL`は`?port=5433`という例になっているが、これは他の
> PostgreSQLプロセスとポートが衝突した場合の例であり、通常の単体インストールでは標準の
> `5432`になる。`psql -d momotools -c '\conninfo'`で実際のポートを確認し、`5432`の場合は
> `?port=`部分ごと削除してよい。

### 6. 依存関係のインストールとマイグレーション

上記「Linux環境構築手順」5.と同じ。

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser   # 任意（Django管理画面 /admin/ 用）
```

### 7. （任意）コード品質チェックツールの有効化

```bash
uv run pre-commit install   # git commit時に自動実行させる場合
```

### 8. 起動確認

```bash
uv run python manage.py runserver 0.0.0.0:8000
```

ブラウザで`http://127.0.0.1:8000/admin/`にアクセスし、6.で作成した管理ユーザーでログインできれば
セットアップ完了。WSL2はデフォルトで`localhost`がWindows側からWSL2側へ自動転送されるため、
Windows側のブラウザからも`127.0.0.1`でアクセスできる。転送が効かない場合は`hostname -I`で
WSL2のIPアドレスを確認し、`http://<そのIP>:8000/admin/`を試す。
