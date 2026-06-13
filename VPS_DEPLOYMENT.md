# VPS deployment

Render からシンVPSへ移行し、GitHub の `main` ブランチへ push したら VPS 上のコードを自動更新する構成です。

既存の Nuxt3 プロジェクトとは分離して動かします。Python のライブラリはグローバル環境へ入れず、`/opt/fanza_api/venv` の仮想環境だけにインストールします。

## 1. VPS 初回セットアップ

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip

sudo useradd -r -m -s /bin/bash fanzaapi
sudo mkdir -p /opt/fanza_api
sudo chown -R fanzaapi:fanzaapi /opt/fanza_api
```

VPS から GitHub を pull できるように、`fanzaapi` ユーザーへ GitHub の deploy key か読み取り権限のある SSH キーを設定してください。

Nuxt3 側と競合させないため、以下は避けてください。

- Nuxt3 のプロジェクトディレクトリ配下へこのリポジトリを clone しない
- `sudo pip install` や `pip install --user` で依存を入れない
- Nuxt3 の systemd service と同じ service 名・同じ作業ディレクトリを使わない

リポジトリを配置します。

```bash
sudo -u fanzaapi git clone git@github.com:<owner>/<repo>.git /opt/fanza_api
cd /opt/fanza_api
sudo -u fanzaapi bash deploy/update.sh
```

## 2. VPS の環境変数

VPS 上で `/opt/fanza_api/.env` を直接作成します。

```bash
sudo -u fanzaapi nano /opt/fanza_api/.env
sudo chmod 600 /opt/fanza_api/.env
sudo chown fanzaapi:fanzaapi /opt/fanza_api/.env
```

VPS 上で実行する場合は、PostgreSQL も同じ VPS 内にある前提で以下を設定します。

```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_SSL=false
DB_SSH_TUNNEL=false
```

ローカルPCからVPS内DBへ接続する場合は、ローカルの `.env` にSSH鍵パスを書きます。`DB_SSH_TUNNEL` は未設定または `auto` なら、鍵ファイルが存在する時だけ自動でSSHトンネルを使います。

```env
DB_SSH_TUNNEL=auto
DB_SSH_HOST=162.43.78.168
DB_SSH_USER=root
DB_SSH_PORT=22
DB_SSH_KEY_PATH=C:\Users\shota\.ssh\uraaka-times-shin-vps.pem
DB_SSH_REMOTE_HOST=127.0.0.1
DB_SSH_REMOTE_PORT=5432
```

## 3. systemd timer

定期実行用の unit を配置します。

```bash
sudo cp /opt/fanza_api/deploy/fanza-api-batch.service /etc/systemd/system/
sudo cp /opt/fanza_api/deploy/fanza-api-batch.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fanza-api-batch.timer
```

実行時刻は `deploy/fanza-api-batch.timer` の `OnCalendar` を変更してください。手動実行とログ確認は以下です。

```bash
sudo systemctl start fanza-api-batch.service
journalctl -u fanza-api-batch.service -n 100 --no-pager
systemctl list-timers fanza-api-batch.timer
```

ファイルログは `/opt/fanza_api/logs` に出力されます。

```bash
ls -lah /opt/fanza_api/logs
tail -f /opt/fanza_api/logs/batch_run.log
tail -f /opt/fanza_api/logs/fetch_fanza_rank.log
tail -f /opt/fanza_api/logs/fetch_antenna_rss.log
tail -f /opt/fanza_api/logs/fetch_fc2_videos.log
```

## 4. GitHub Secrets

GitHub リポジトリの `Settings > Secrets and variables > Actions` に以下を登録します。

- `VPS_HOST`: VPS のホスト名または IP
- `VPS_USER`: SSH 接続ユーザー
- `VPS_SSH_KEY`: SSH 秘密鍵
- `VPS_PORT`: SSH ポート。省略時は `22`
- `APP_DIR`: VPS 上の配置先。省略時は `/opt/fanza_api`
- `DEPLOY_BRANCH`: デプロイするブランチ。省略時は `main`

push 後に `.github/workflows/deploy-vps.yml` が実行され、VPS 上で `deploy/update.sh` を実行します。
