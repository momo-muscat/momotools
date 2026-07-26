# 別PC（Docker運用で動いている方）のDocker撤去手順

このPC（`/home/momo/momotools`）では、Docker撤去 → ネイティブ構成（uv + PostgreSQL +
systemd/直接実行）への移行が完了済み（詳細は`CLAUDE.md`・`README_VPS.md`§10参照）。
もう1台のPC（今もDocker Composeでmomotoolsを動かしている方）で同じ移行を行うための手順。

## ⚠️ 最重要: 全ての作業はWSL2の素のターミナルで行うこと

今回の一連の作業で、**Dev Container（VS Codeの「Reopen in Container」）内で
git操作やファイル編集を行ったことが原因で、`.git`やファイルがrootオーナーになり
`git commit`ができなくなる**という問題が繰り返し発生した。原因は、コンテナの
デフォルト実行ユーザーがrootで、`.:/app`のbind mountを通じてホスト側にも
rootオーナーのファイルができてしまうこと。

**このドキュメントのコマンドは、全て以下の方法でのみ実行すること:**

- ✅ WSL2のターミナル（Windows Terminal、`wsl.exe`、VS Codeの「Remote - WSL」で開いた
  通常のターミナルなど）
- ❌ VS Codeで「Dev Containers: Reopen in Container」を選んだ状態のターミナル
- ❌ `docker compose exec web bash`等でコンテナ内に入った状態

作業中にVS Codeが「Reopen in Container」を提案してきても**選ばないこと**。
もし誤って一度でもDev Container内でこのリポジトリを触ってしまったら、
`ls -la`で`.git`やファイルの所有者を確認し、rootオーナーのものがあれば
`sudo chown -R <OSユーザー名>:<OSユーザー名> ~/momotools`で戻すこと。

各コマンドブロックの先頭に **[WSL]** と明記する。

---

## 0. 前提確認

**[WSL]**

```bash
whoami          # このPCのOSユーザー名を確認（後でPostgreSQLロール名に使う）
cd ~/momotools
git status
docker compose ps
```

- OSユーザー名をメモしておく（このPCの`momo`相当。違う名前なら以降`momo`と書いている箇所を読み替える）
- `docker compose ps`で`web`/`db`が動いているか確認

## 1. （必要なら）ローカルDBデータのバックアップ

開発用の使い捨てデータしか無ければスキップしてよい。残しておきたいデータがあれば取得する。

**[WSL]**

```bash
cd ~/momotools
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > ~/momotools_local_backup_$(date +%Y%m%d).sql
```

## 2. 最新のリポジトリを取得（Docker撤去後の内容）

**[WSL]**

```bash
cd ~/momotools
git pull
```

`Dockerfile` / `docker-compose.yml` / `docker-compose.prod.yml` / `.devcontainer/` が
削除され、`CLAUDE.md`・`README.md`・`.env.example`等がネイティブ構成向けに
書き換わっていることを確認する。

## 3. ネイティブPostgreSQLのインストール + ロール/DB作成

**[WSL]**

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
psql --version
```

OSユーザー名と同じ名前のロールを作る（peer認証、パスワード不要）。

```bash
sudo -u postgres createuser --createdb <OSユーザー名>
sudo -u postgres createdb momotools --owner=<OSユーザー名>
psql -d momotools -c '\conninfo'
```

> `\conninfo`で表示される`Server Port`が`5432`でない場合（他のPostgreSQLと衝突して
> `5433`等になることがある）、そのポート番号を次のステップの`.env`で使う。

もし1.でバックアップを取った場合はここで復元する。

```bash
psql -d momotools -f ~/momotools_local_backup_*.sql
```

## 4. `.env`の作成・更新

**[WSL]**

```bash
cd ~/momotools
cp .env.example .env
```

`DATABASE_URL`のロール名部分を、3.で作成したOSユーザー名に置き換える。
ポートが5432でなければ`?port=<実際のポート>`を末尾に付ける。

```
DATABASE_URL=postgres://<OSユーザー名>@//var/run/postgresql/momotools
```

## 5. 古い`.venv`/`staticfiles`のroot所有権を解消

Docker運用時に`venv_data`という名前付きボリュームで`.venv`をコンテナ内(root)から
書き込んでいたため、ホスト側では`.venv`がrootオーナーになっている。
`uv sync`が`Permission denied`で失敗する場合はこれが原因。

**[WSL]**

```bash
ls -la ~/momotools/.venv
# root:root になっていたら削除して作り直す
sudo rm -rf ~/momotools/.venv
```

`staticfiles/`も同様にDockerのrootで生成されていた場合は削除してよい（再生成可能）。

```bash
sudo rm -rf ~/momotools/staticfiles
```

## 6. 依存関係インストール・マイグレーション・動作確認

**[WSL]**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # 未導入なら
source $HOME/.local/bin/env
cd ~/momotools
uv sync
uv run python manage.py migrate
uv run python manage.py runserver 0.0.0.0:8000
```

`http://localhost:8000/momotools/`が表示されればOK。
（ポート8000がまだDockerの`web`コンテナに使われている場合は`docker compose stop web`
してから試す、または`0.0.0.0:8001`で試す）

## 7. Dockerコンテナ・イメージ・ボリュームの削除

サイト動作確認ができたら、Docker関連のコンテナ・イメージ・ボリュームを削除する。

**[WSL]**

```bash
cd ~/momotools
docker compose down
docker volume ls | grep momotools
docker volume rm momotools_postgres_data momotools_venv_data   # 実際の名前に合わせる
docker images | grep momotools
docker rmi momotools-web:latest
```

## 8. Docker Engine本体のアンインストール

このPCで他にDockerを使っているプロジェクトが無いことを確認してから実行する。

**[WSL]**

```bash
sudo systemctl disable --now docker.service docker.socket containerd.service
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
sudo apt-get autoremove -y --purge
```

`/var/lib/docker`が独立したディスク（別パーティション）としてマウントされている
ことがある。削除前に確認する。

```bash
mount | grep -i docker
findmnt /var/lib/docker
```

マウントポイントであれば先にアンマウントしてから削除する。

```bash
sudo umount /var/lib/docker   # マウントされていた場合のみ
sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc
sudo groupdel docker   # 存在すれば
```

最終確認:

```bash
which docker
dpkg -l | grep -E 'docker-ce|containerd'
getent group docker
```

全て「何も表示されない」ことを確認する。

## 9. git push/pullの認証確認

Dev Containerを使ったことがある場合、VS Code経由のgit認証情報ヘルパーに依存していて、
コンテナが無くなると素のWSLから`git push`できなくなることがある
（`fatal: could not read Username for 'https://github.com'`のようなエラー）。

**[WSL]**

```bash
cd ~/momotools
git push origin main --dry-run
```

エラーが出る場合はGitHub CLIで認証する。

```bash
sudo apt-get install -y gh
gh auth login       # GitHub.com → HTTPS → Yes → Login with a web browser
gh auth setup-git
git push origin main
```

## 10. VS Codeの開き方を変更

`.devcontainer/`は削除済みなので「Reopen in Container」は今後表示されなくなるはずだが、
念のため：VS Codeでこのフォルダを開くときは **「Remote - WSL」拡張機能で通常のWSLフォルダ
として開く**（Dev Containersではない）。

---

## 完了確認チェックリスト

- [ ] `git pull`で最新のネイティブ構成が取得できている
- [ ] `uv run python manage.py runserver`でサイトが表示できる
- [ ] `docker compose ps`が「no configuration file provided」等になる（コンテナ無し）
- [ ] `which docker`が何も返さない
- [ ] `git push`が素のWSLから成功する
