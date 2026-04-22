# Changelog

## 3.0.0

- Rebranded the app as Easy Localhost v3 and aligned the UI, README, executable metadata, and release versioning.
- Rebuilt the desktop interface around a graphite and lime visual system with cleaner spacing, sharper borders, and more restrained action colors.
- Replaced the old icon with a new monogram `EL` mark used in the window, header, executable, and release assets.
- Added a single-cycle refresh control that rotates through `Auto`, `10s`, `5s`, and `Manual`.
- Added a `RefreshMode` model with test coverage for cycle order and interval behavior.
- Redesigned folder groups so collapsed projects stay compact, show summary chips, and can be expanded by clicking the whole header.
- Added pure presentation-state helpers with tests for default expansion and compact port summaries.
- Added Windows version metadata to the PyInstaller build and documented the SmartScreen limitation more precisely.
- Added a v3 UI preview image for public docs and release notes.

## 1.2.1

- Reworked the process display into high-contrast rows so ports and processes are immediately visible.
- Switched the visual palette to pure black plus cacao, sand, warm brown, sage, and soft aqua tones.
- Kept active groups open by default while leaving groups without active ports collapsed.
- Added clearer action color separation for Open, Copy, Source, and Close.
- Regenerated the app icon with a cleaner localhost panel shape and earth-tone palette.

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
