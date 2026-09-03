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


# WSLディストリビューションの丸ごと移行（エクスポート／インポート）

上記「別PCでの環境構築手順」はGitHubのリポジトリのみを移す方法であり、OS側の環境
（PostgreSQL、uv、各種CLIツール、シェル設定など）は移行先PCで再構築する必要がある。

これに対し、WSLディストリビューションを丸ごとtarにエクスポートして移行先PCへインポートすれば、
インストール済みパッケージ・DBの実データ・ホームディレクトリを含めた環境全体をそのまま複製できる。

| 方式 | 移るもの | 向いている場面 |
| --- | --- | --- |
| リポジトリのクローン（別PCでの環境構築手順） | ソースコードのみ | 移行先のOS環境が既に整っている／クリーンな環境で作り直したい |
| ディストリビューションのエクスポート／インポート | OS環境まるごと（パッケージ・DBデータ・ホーム含む） | PC入れ替え、環境の完全複製、バックアップ |

> エクスポートしたtarには`.env`やDBの実データ、SSH鍵、シェル履歴などの秘密情報がそのまま含まれる。
> 受け渡し時の取り扱いに注意し、クラウドストレージ等に平文で置いたままにしない。

### 1. 移行元PCでのエクスポート

対象ディストリビューションを停止してからエクスポートする（稼働中でも実行できるが、
DBの書き込み中などに実行すると不整合が生じうるため停止を推奨）。

```powershell
wsl -l -v                       # 対象名とSTATEを確認
wsl --terminate Ubuntu-26.04    # 停止（またはwsl --shutdownで全停止）
wsl --export Ubuntu-26.04 D:\WSL\Ubuntu-26.04_20260816.tar
```

ファイル名に日付を入れておくと世代管理しやすい。エクスポートには数分かかり、
本プロジェクトの環境では約4.9GBのtarになった。

> 圧縮したい場合は`--format tar.gz`（または`tar.xz`）を付ける。サイズは小さくなるが
> エクスポート・インポートともに時間が延びる。VHDXのまま持ち出す`--format vhd`もある。
>
> ```powershell
> wsl --export Ubuntu-26.04 D:\WSL\Ubuntu-26.04.tar.gz --format tar.gz
> ```

### 2. tarファイルの受け渡し

外付けドライブ、ファイル共有、クラウドストレージ等で移行先PCへコピーする。
容量が大きいため、ネットワーク経由の場合は転送時間を見込んでおくこと。

### 3. 移行先PCでのインポート

事前に移行先PCでWSL自体を有効化しておく（「Linux環境構築手順」1.参照）。
その上で、インポート先ディレクトリとtarのパスを指定して実行する。

```powershell
wsl --import Ubuntu-26.04 D:\WSL\Ubuntu-26.04 D:\WSL\Ubuntu-26.04_20260816.tar --version 2
```

- 第1引数: 新しいディストリビューション名（既存名と重複不可）
- 第2引数: 実体（`ext4.vhdx`）を置くディレクトリ。**存在しない場合は自動作成される**
- 第3引数: インポート元のtarのパス

インポート先はtarと同じフォルダを指定しないこと。専用のサブディレクトリを切る
（例のように`D:\WSL\Ubuntu-26.04`）。

> インポート先ドライブの空き容量に注意。展開後のVHDXはtarより大きくなる
> （本プロジェクトでは4.9GBのtarに対しVHDXは約5.3GB）。

### 4. インポート後の確認

```powershell
wsl -l -v                            # 一覧に追加され、VERSIONが2であることを確認
wsl -d Ubuntu-26.04                  # 起動
```

ディストリビューション内で以下を確認する。

```bash
whoami                    # 既定ユーザーがmomoであること（rootならば下記の対処を行う）
cat /etc/wsl.conf         # systemd有効・既定ユーザー設定の確認
psql -d momotools -c '\conninfo'   # PostgreSQLのデータが移行できていること
```

> **既定ユーザーがrootになる場合の対処**
>
> `--import`したディストリビューションは、既定ユーザーの情報がtarに含まれていないと
> rootでログインする状態になる。ディストリビューション内に`/etc/wsl.conf`があり、
> 以下の記述があればユーザー設定はそのまま引き継がれる（本プロジェクトの環境は該当）。
>
> ```ini
> [boot]
> systemd=true
>
> [user]
> default=momo
> ```
>
> rootになってしまう場合は、`/etc/wsl.conf`に上記`[user]`セクションを追記して
> `wsl --terminate Ubuntu-26.04`で再起動するか、Windows側から次を実行する。
>
> ```powershell
> wsl --manage Ubuntu-26.04 --set-default-user momo
> ```

### 5. 移行後の後始末

動作確認が済んだら、移行元PCの旧ディストリビューションとtarを整理する。

```powershell
wsl --unregister Ubuntu-26.04   # 登録解除。VHDXごと完全に削除されるため実行前に必ず確認
```

> `--unregister`は取り消しできない。移行先での動作確認が完全に終わり、
> エクスポートしたtarをバックアップとして保持していることを確認してから実行する。

インポートに使ったtarは、しばらくバックアップとして残しておくとよい。


# WSLディストリビューションの実体（VHDX）の移動

ディストリビューションの実体は`ext4.vhdx`という単一のファイルで、既定では
Cドライブの`%LOCALAPPDATA%\wsl\{GUID}\`配下に作成される。開発を進めるとこのファイルは
数GB〜数十GBに膨らむため、Cドライブの容量を圧迫する場合はDドライブ等へ移動する。

### 1. 現在の保存場所を調べる

保存場所はレジストリの`HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss`配下に
ディストリビューションごとのサブキーとして記録されている。PowerShellで一覧化できる。

```powershell
Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath
  [PSCustomObject]@{ Name = $p.DistributionName; BasePath = $p.BasePath }
} | Format-Table -AutoSize
```

出力例:

```
Name         BasePath
----         --------
Ubuntu       D:\WSL\Ubuntu
Ubuntu-26.04 D:\WSL\Ubuntu-26.04
```

### 2. 既存ディストリビューションを移動する

`wsl --manage --move`を使う（WSL 2.x）。**ディストリビューション名・既定ユーザー・
`/etc/wsl.conf`の設定はすべて維持され**、レジストリのパスも自動で書き換わる。
エクスポート／インポートし直す必要はない。

```powershell
wsl --terminate Ubuntu                       # 対象を停止
wsl --manage Ubuntu --move D:\WSL\Ubuntu     # 移動
```

移動後は上記1.のコマンドで`BasePath`が変わったことを確認する。

> 移動元フォルダに`shortcut.ico`（約37KB）が残ることがある。`ext4.vhdx`さえ移動できていれば
> 実害はないので、気になる場合のみ移動元フォルダごと削除してよい。
> ただし親フォルダ`%LOCALAPPDATA%\wsl`自体は残しておくこと。

### 3. 新規インストール先を指定する

**WSLには既定のインストール先を恒久的に変更する設定項目が存在しない**
（`.wslconfig`はメモリ・CPU・ネットワーク等のVM設定用で、インストール先の項目は持たない）。
そのため、Cドライブ以外に入れたい場合は毎回`--location`で明示する。

```powershell
wsl --install Ubuntu-26.04 --location D:\WSL\Ubuntu-26.04
```

`--import`の場合は第2引数がそのまま保存先になる（上記「3. 移行先PCでのインポート」参照）。

指定を忘れてCドライブに入れてしまった場合も、上記2.の`--move`で後から移動できる。

### 4. Windows側からディストリビューション内のファイルにアクセスする

エクスプローラーやWindowsのツールからは、UNCパス経由でアクセスする。

```
\wsl.localhost\Ubuntu-26.04\home\momo\momotools
```

`\wsl$\Ubuntu-26.04\...`という旧形式も使えるが、`wsl.localhost`が現在の推奨形式。
ドライブレターに割り当てることもできる。

```powershell
net use L: \wsl.localhost\Ubuntu-26.04 /persistent:yes
```

WSL側から現在のディレクトリをエクスプローラーで開く場合は次のとおり。

```bash
explorer.exe .
```

> **`ext4.vhdx`を直接操作しないこと。** Windowsのツールでコピー・編集・移動すると
> ファイルシステムが破損する。ファイル操作は必ず上記のUNCパス経由か、
> ディストリビューション内から行う。VHDXの移動が必要な場合は上記2.の`--move`を使う。
