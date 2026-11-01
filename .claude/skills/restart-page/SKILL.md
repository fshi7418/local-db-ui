---
name: restart-page
description: Restart the local-db-ui Dash app so code changes take effect. Use only when the user explicitly asks to restart the page, app, or UI, including when they ask for a change and a restart together.
---

# Restart the page

Run this only when the user asks for a restart. If they also asked for a code change, make and check the change first, then restart.

1. Restart the service:

   ```bash
   systemctl --user restart local-db-ui.service
   ```

2. Confirm the app is serving again, retrying while it starts:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' --retry 15 --retry-delay 1 --retry-connrefused http://127.0.0.1:8050/
   ```

   If this doesn't print `200`, read the recent logs and tell the user what failed:

   ```bash
   journalctl --user -u local-db-ui.service -n 30 --no-pager
   ```

Tell the user whether the service is running again.
