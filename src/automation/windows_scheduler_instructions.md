# Weekly Automation with Windows Task Scheduler

## Option A — GUI (Create Basic Task)

1. Open **Task Scheduler** (search it in the Start menu).
2. Click **Create Basic Task…**
3. **Name:** `Weekly Journal Digest`. Click Next.
4. **Trigger:** choose **Weekly** → pick a day (e.g. Sunday) and time (e.g. 08:00).
5. **Action:** **Start a program**.
6. **Program/script:** full path to your Python, e.g.
   `C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe`
   (or the venv one: `C:\path\to\weekly_journal_digest\.venv\Scripts\python.exe`).
7. **Add arguments:**
   ```
   -m src.main
   ```
8. **Start in (important!):** the project root so `src` is importable:
   ```
   C:\path\to\weekly_journal_digest
   ```
9. Finish. Right-click the task → **Run** to test it.

> Find your Python path with PowerShell: `(Get-Command python).Source`

## Option B — PowerShell (one command)

Run PowerShell **as the current user** from the project root:

```powershell
$python  = (Get-Command python).Source
$project = (Get-Location).Path
$action  = New-ScheduledTaskAction -Execute $python -Argument "-m src.main" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 8:00am
Register-ScheduledTask -TaskName "WeeklyJournalDigest" -Action $action -Trigger $trigger -Description "Weekly Journal Digest"
```

## Secrets

Set the SMTP app password as a user environment variable (persists across
reboots) so it is not stored in the repo:

```powershell
setx DIGEST_SMTP_PASSWORD "your-app-password"
```

(Reopen the terminal / re-run after `setx`; Task Scheduler picks up user env
vars for tasks run as that user.)

## Verify / debug

```powershell
# Manual dry run:
python -m src.main --dry-run
# Inspect the task:
Get-ScheduledTask -TaskName "WeeklyJournalDigest" | Get-ScheduledTaskInfo
```

Logs are written to `logs\weekly_run.log` and `logs\errors.log` in the project
directory.
