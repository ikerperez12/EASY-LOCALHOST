# Changelog

## 1.0.1

- Added automated local and CI security checks with Bandit and pip-audit.
- Replaced direct subprocess browser launching with the standard `webbrowser` API.
- Replaced URL-based health probing with `http.client` constrained to `127.0.0.1`.
- Hardened build script error handling and stale executable cleanup.
- Confirmed no known dependency vulnerabilities and no static security findings.

## 1.0.0

- Initial public release.
- Live localhost monitoring.
- Project detection from Git roots, package metadata, and common project markers.
- Compact always-on-top Windows UI.
- Open, copy, source-folder, and close actions.
- Portable Windows executable build with PyInstaller.
