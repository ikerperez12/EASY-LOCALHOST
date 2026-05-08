# 05 - Decision Log

## 2026-05-08

- Decision: change default group behavior from auto-open active groups to all-collapsed.
- Reason: dense sessions with many active localhost ports should remain calm and user-controlled.

- Decision: prefer exact command files in the UI when they exist.
- Reason: showing only a broad directory makes it harder to identify the actual server entrypoint.

- Decision: keep GitHub Releases as the deployment path.
- Reason: Easy Localhost is a Windows desktop utility, not a web app.

- Decision: compress the `3.0.3` header and move global expand/collapse actions into the summary bar.
- Reason: the app is intended to stay always-on-top, so primary chrome must be useful without occupying excessive screen area.
