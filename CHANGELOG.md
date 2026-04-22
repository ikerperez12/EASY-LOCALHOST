# Changelog

## 1.2.0

- Fixed the flat-list regression by replacing the port list with folder/project-based collapsible groups.
- Added stable scroll restoration so auto-refresh does not reset the user's scroll position.
- Changed auto-refresh to a calmer 7-second default and added manual 5s/10s interval controls.
- Added a clear manual reload action.
- Improved dense-session readability by showing process/PID details inside each folder group.
- Documented the Microsoft SmartScreen limitation for unsigned portable Windows executables.

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
