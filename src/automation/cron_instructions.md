# Weekly Automation with cron (macOS & Linux)

macOS and Linux both use `cron`. The same steps work on local machines and on
cloud servers (AWS EC2, Azure VM, GCP Compute Engine, DigitalOcean, Linode,
OVH, ...).

## 1. Find your Python and project paths

```bash
which python3                 # e.g. /usr/bin/python3 or /path/to/.venv/bin/python
pwd                           # run inside the project root
```

Prefer the virtualenv interpreter if you created one:
`/path/to/weekly_journal_digest/.venv/bin/python`.

## 2. Edit the crontab

```bash
crontab -e
```

## 3. Add a weekly schedule (example: every Sunday at 08:00)

```cron
0 8 * * SUN cd /path/to/weekly_journal_digest && /path/to/python -m src.main >> logs/cron.out 2>&1
```

Notes:
- Use **absolute paths** for both the interpreter and (via `cd`) the project.
- `-m src.main` must run from the project root, hence the `cd`.
- Secrets: cron has a minimal environment. Provide the SMTP app password via an
  env var on the same line, or keep it in `config/user_config.yaml`:

```cron
0 8 * * SUN cd /path/to/weekly_journal_digest && DIGEST_SMTP_PASSWORD='app-password' /path/to/python -m src.main >> logs/cron.out 2>&1
```

## 4. Verify

```bash
crontab -l                    # list installed jobs
# Force a test run now:
cd /path/to/weekly_journal_digest && python -m src.main --dry-run
```

## Cloud / server tips

- Ensure Python + dependencies are installed for the cron user
  (`pip install -r requirements.txt`).
- Ensure the project directory is readable/writable by the cron user.
- Persist logs to a durable directory. A common convention:
  `/var/log/journal_digest/` — create it and point the redirect there:

```bash
sudo mkdir -p /var/log/journal_digest && sudo chown "$USER" /var/log/journal_digest
```

```cron
0 8 * * SUN cd /path/to/weekly_journal_digest && /path/to/python -m src.main >> /var/log/journal_digest/cron.out 2>&1
```

- **Docker:** run cron on the host (calling `docker run ... python -m src.main`),
  or run a lightweight cron service inside the container. Mount the config and
  logs as volumes so they persist.

## Time zones

`cron` uses the server's local time zone. On cloud servers this is often UTC —
set the hour accordingly or change the server TZ (`timedatectl set-timezone`).
