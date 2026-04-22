# Changelog

## 1.1.0

- Redesigned the desktop interface with a pure black base and sunset/lavender/mauve palette.
- Increased corner radii, strengthened borders, and improved visual hierarchy for a more premium compact widget.
- Added a new shared app icon and wired it into the window UI, embedded executable icon, and packaged assets.
- Included icon assets in the PyInstaller one-file build so the packaged app uses the same branding at runtime.
- Versioned the PyInstaller spec so the public repo can reproduce the packaged executable.
- Revalidated tests, static security scan, dependency audit, packaged executable startup, and real localhost detection.

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
