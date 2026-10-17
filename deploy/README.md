# Operations

How Bill Mitra runs in production, and the scripts that keep it running.

## Layout on the VM

The app runs on a shared GCP VM with about 20 other apps. Everything here touches only `/opt/bill-mitra` and the
`bill-mitra` compose service. Never run `docker system prune`, `docker compose down` without `-f compose.yml`, or
anything else that reaches other containers.

```
/opt/bill-mitra/
  src/          git clone of this repo
  compose.yml   one service, container port 8000 on 127.0.0.1:8021
  .env          settings and keys (never committed)
  data/         billmitra.db and media/, owned by uid 1000, mounted at /srv/backend/var
  backups/      created by backup.sh, root only
  run/          watchdog state
```

Public URL: https://aikam.tryaiplanet.com, health at `/api/health`.

## Scripts

| Script | What it does |
| --- | --- |
| `backup.sh` | Online SQLite backup (backup API, safe while the app runs) checked with `PRAGMA integrity_check`, plus a tar of `media/`. Writes `backups/billmitra-db-<UTC stamp>.sqlite3.gz` and `backups/billmitra-media-<UTC stamp>.tar.gz`, deletes local backups older than 14 days, and copies to `BACKUP_BUCKET` with `gsutil` when that is set. |
| `watchdog.sh` | Calls `http://127.0.0.1:8021/api/health` with a 10 second timeout. Counts failures in `run/watchdog.failures`. On the third failure in a row it runs `docker compose -f compose.yml restart bill-mitra` and logs it. |
| `deploy.sh` | Runs `backup.sh`, then `git -C src pull --ff-only` and `docker compose -f compose.yml up -d --build`, then waits up to 180 seconds for the health check. Exits non-zero if any step fails or the app never turns healthy. |

All three log one timestamped line per step and exit non-zero on failure. Paths and limits can be changed with
the environment variables listed at the top of each script.

The VM needs `python3`, `curl`, `setpriv` (util-linux) and `gzip`, which Debian and Ubuntu images ship with.
`gsutil` is needed only if `BACKUP_BUCKET` is set.

## Install the cron jobs

1. Make the log folder:
   ```bash
   sudo mkdir -p /var/log/bill-mitra
   ```
2. Install the cron file (it runs as root):
   ```bash
   sudo install -m 644 -o root -g root /opt/bill-mitra/src/deploy/crontab.example /etc/cron.d/bill-mitra
   ```
3. To copy backups off the VM, set `BACKUP_BUCKET=gs://<bucket>/bill-mitra` in `/etc/cron.d/bill-mitra`. The
   VM's service account needs write access to that bucket.
4. Run each script once by hand to check it:
   ```bash
   sudo /opt/bill-mitra/src/deploy/backup.sh
   sudo /opt/bill-mitra/src/deploy/watchdog.sh
   sudo ls -l /opt/bill-mitra/backups
   ```
5. Keep the logs from growing forever, for example `/etc/logrotate.d/bill-mitra`:
   ```
   /var/log/bill-mitra/*.log {
       weekly
       rotate 8
       compress
       missingok
       notifempty
   }
   ```

Logs: `/var/log/bill-mitra/backup.log` and `/var/log/bill-mitra/watchdog.log`. The cron jobs:

```
30 2 * * * root flock -n /run/bill-mitra-backup.lock /opt/bill-mitra/src/deploy/backup.sh >> /var/log/bill-mitra/backup.log 2>&1
* * * * *  root flock -n /run/bill-mitra-watchdog.lock /opt/bill-mitra/src/deploy/watchdog.sh >> /var/log/bill-mitra/watchdog.log 2>&1
```

## Deploy

Manual deploy is the default. Reach the VM through gcloud IAP as today, then:

```bash
/opt/bill-mitra/src/deploy/deploy.sh 2>&1 | sudo tee -a /var/log/bill-mitra/deploy.log
```

It asks for sudo for the backup and docker steps. The plain redeploy command still works if you need it:
`cd /opt/bill-mitra && git -C src pull && sudo docker compose -f compose.yml up -d --build`.

## Restore a backup

1. Pick the backup to restore:
   ```bash
   sudo ls -lt /opt/bill-mitra/backups
   ```
2. Stop only the bill-mitra container:
   ```bash
   cd /opt/bill-mitra && sudo docker compose -f compose.yml stop bill-mitra
   ```
3. Keep the current data aside, in case you need to go back:
   ```bash
   sudo cp -a /opt/bill-mitra/data /opt/bill-mitra/data.before-restore-$(date -u +%Y%m%d-%H%M%S)
   ```
4. Restore the database. Remove the old WAL files first, or SQLite will replay them over the restored file:
   ```bash
   sudo rm -f /opt/bill-mitra/data/billmitra.db-wal /opt/bill-mitra/data/billmitra.db-shm
   sudo sh -c 'gunzip -c /opt/bill-mitra/backups/billmitra-db-<stamp>.sqlite3.gz > /opt/bill-mitra/data/billmitra.db'
   ```
5. Restore media (optional, only if files were lost):
   ```bash
   sudo rm -rf /opt/bill-mitra/data/media
   sudo tar -xzf /opt/bill-mitra/backups/billmitra-media-<stamp>.tar.gz -C /opt/bill-mitra/data
   ```
6. Give the files back to the container user:
   ```bash
   sudo chown -R 1000:1000 /opt/bill-mitra/data
   ```
7. Start the container and check health:
   ```bash
   sudo docker compose -f compose.yml start bill-mitra
   curl -fsS http://127.0.0.1:8021/api/health
   ```
8. Once you are sure the restore is good, delete the `data.before-restore-*` copy (it holds consumer data).

To restore from the bucket, first copy the files down with
`sudo gsutil cp gs://<bucket>/bill-mitra/billmitra-db-<stamp>.sqlite3.gz /opt/bill-mitra/backups/`.

## GitHub Actions

- `ci.yml`: pytest and ruff for the backend, typecheck, lint and build for the frontend, on every push and pull
  request.
- `uptime.yml`: checks `https://aikam.tryaiplanet.com/api/health` every 15 minutes with retries. A failed run
  means the site is down, and GitHub emails whoever last edited the schedule. GitHub pauses scheduled workflows
  after 60 days without commits, so re-enable it in the Actions tab if that happens.
- `deploy.yml`: on manual dispatch, or after CI passes on a push to `main`, runs `deploy.sh` on the VM over SSH.

The VM is reached through gcloud IAP today and has no SSH open to the internet, so `deploy.yml` skips itself with
a notice unless these repository secrets exist:

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | address the runner can reach over SSH |
| `DEPLOY_USER` | user with passwordless sudo for `docker` and `deploy/backup.sh` |
| `DEPLOY_SSH_KEY` | private key for that user, used only for deploys |
| `DEPLOY_KNOWN_HOSTS` | optional, the host's `known_hosts` line, so the runner does not trust the first key it sees |

They are optional. Manual deploy stays the default.
