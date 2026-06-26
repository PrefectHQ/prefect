# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.x     | :white_check_mark: |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |
| 0.x     | :x:                |

## Reporting a Vulnerability

Please report security vulnerabilities privately using [GitHub's security advisory feature](https://github.com/PrefectHQ/prefect/security/advisories/new). Do not open public issues for security concerns.

## Scope

We accept reports for vulnerabilities in Prefect code and products maintained in this repository, including the Python SDK, self-hosted server/API, and web UI.

The following are **out of scope**:

- Vulnerabilities in third-party dependencies. We'll bump version floors for known CVEs, but the fix belongs upstream.
- Issues that require the attacker to already have server-side access or control of the Prefect server configuration.

## Disclosure Process

When we receive a valid report:

1. We triage the report and determine whether it affects Prefect directly.
2. We develop and test a fix on a private branch.
3. We coordinate CVE assignment through GitHub's advisory process when warranted.
4. We publish the advisory and release a patched version.
5. We credit the reporter in the advisory (unless they prefer otherwise).
