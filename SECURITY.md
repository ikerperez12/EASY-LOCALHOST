# Security Policy

## Scope

Easy Localhost is designed to be safe for public source distribution and safe to run locally:

- no external network calls
- no telemetry
- no credential storage
- no project file modification
- no code injection into other processes
- no privileged operations except optional process termination allowed by Windows

## Reporting

If you discover a security issue, open a private report if possible before publishing full details.

Include:

- affected version or commit
- reproduction steps
- expected impact
- whether the issue requires local access, admin rights, or user interaction

## Hard Boundaries

The application should remain limited to:

- reading localhost listening ports
- reading process metadata
- reading project root markers
- opening localhost URLs
- opening local folders
- terminating a selected local process tree

Any change that expands beyond that should be treated as a security-sensitive design change.
