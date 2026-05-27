# Audit-log retention rollout

This runbook covers the operator side of Phase 9's audit-log
retention enforcement (`scripts/audit-log-retention.py`).

## What the script does

* Connects to each provided service DB.
* Counts `audit_log` rows older than the retention cutoff (default
  2 years per `docs/compliance/retention-policy.md`).
* If `--dry-run`, reports the count and exits.
* Otherwise deletes in 5,000-row batches with per-batch transactions
  so a runaway purge doesn't lock the table.
* Hard safety cap of 1,000,000 rows per invocation. Past that, the
  script aborts and exits 3 — investigate before raising.

## First-time rollout

1. **Manual dry-run** to confirm the script reads what you expect:
   ```bash
   python scripts/audit-log-retention.py \
       --db-url postgresql://eduzim:$DB_PASSWORD@postgres:5432/academics_db \
       --db-url postgresql://eduzim:$DB_PASSWORD@postgres:5432/auth_db \
       --dry-run
   ```
   Expected log line per DB:
   `audit-retention <url>: N row(s) eligible (dry-run=True)`
   On a fresh platform the count is zero; that's the right answer.

2. **Schedule the daily job.** Three reasonable options:

   ### Option A: Kubernetes CronJob
   ```yaml
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: eduzim-audit-retention
   spec:
     schedule: "30 2 * * *"   # 02:30 daily
     jobTemplate:
       spec:
         template:
           spec:
             restartPolicy: OnFailure
             containers:
             - name: retention
               image: ghcr.io/phani3108/eduzim-migrations:${IMAGE_TAG}
               command:
               - python
               - /migrations/scripts/audit-log-retention.py
               - --db-url
               - $(ACADEMICS_DB_URL)
               - --db-url
               - $(AUTH_DB_URL)
               envFrom:
               - secretRef:
                   name: eduzim-db-credentials
   ```

   ### Option B: GitHub Actions schedule
   ```yaml
   on:
     schedule:
       - cron: "30 2 * * *"
   jobs:
     purge:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - run: pip install sqlalchemy psycopg2-binary
         - run: python scripts/audit-log-retention.py
                  --db-url "${{ secrets.ACADEMICS_DB_URL }}"
                  --db-url "${{ secrets.AUTH_DB_URL }}"
   ```

   ### Option C: crond inside the migrations container
   Append to the migrations image's startup:
   ```bash
   (crontab -l ; echo "30 2 * * * python /migrations/scripts/audit-log-retention.py \\
       --db-url \"$DATABASE_URL_ACADEMICS\" \\
       --db-url \"$DATABASE_URL_AUTH\" >> /var/log/audit-retention.log 2>&1") | crontab -
   ```

3. **Monitor the first real run.** Grafana / Loki query for the
   service-name `eduzim-migrations` (or whatever you ran the script
   as) shows the per-DB count + delete batches.

## Day-2 operations

* **Skipped DBs**: if a service hasn't yet added its `audit_log` table,
  the script logs `audit-retention skip <url>: ... no such table` and
  continues. Not an error.
* **Safety-cap hits**: exit code 3. The Slack alert (Phase 6
  Alertmanager — wire a separate rule for retention-job failures)
  fires; operator decides whether the backlog is legitimate (months
  of missed runs) or alarming (a sudden 1M+ audit-row burst means
  something is wrong upstream — investigate before purging).
* **Verifying retention is enforced**: monthly query
  ```sql
  SELECT min(occurred_at) AS oldest, count(*) FROM audit_log;
  ```
  on each service DB. The `oldest` should be < 730 days ago (or one
  day older than that if the cron hadn't run yet today).

## Recovery: I missed retention for a long time

If `--dry-run` reports more than the safety cap:

1. **Don't raise the cap blindly.** Investigate first — is the count
   plausible (months × ~1k/school/day × N schools)?
2. If plausible, **purge in chunks** with a tighter cutoff:
   ```bash
   # First, kill the OLDEST stuff with a much tighter cutoff
   python scripts/audit-log-retention.py \
       --db-url ... \
       --retention-days 1095   # 3 years; this is "purge anything > 3y"
   sleep 60   # let WAL catch up
   python scripts/audit-log-retention.py \
       --db-url ... \
       --retention-days 900
   sleep 60
   python scripts/audit-log-retention.py \
       --db-url ... \
       --retention-days 730    # normal policy
   ```
3. Then schedule the daily job so this doesn't happen again.

## What this script does NOT do

* **It does NOT export audit rows before deleting.** ADR 007 +
  retention policy permit hard delete past the window. If a school
  contract requires longer retention for that school's rows, that's
  a per-tenant override — currently out of scope.
* **It does NOT cascade to derived tables.** The audit_log is a
  leaf table — nothing references it. Deletes are safe.
* **It does NOT respect a `legal_hold` flag.** If a future feature
  needs that (active investigation, etc.), add a `legal_hold`
  column to the audit_log table and `AND NOT legal_hold` to the
  script's DELETE.

## Smoke test for the runbook itself

After scheduling:

1. SSH to the scheduler host.
2. Verify the cron line exists / the k8s CronJob is enabled.
3. Run the job ONCE manually:
   ```bash
   kubectl create job --from=cronjob/eduzim-audit-retention \
       audit-retention-manual-test
   kubectl logs job/audit-retention-manual-test
   ```
4. Confirm exit code 0 and a "0 row(s) eligible" log line (fresh DB).

Once that passes, the runbook is verified.
