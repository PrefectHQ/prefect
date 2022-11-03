---
description: How Prefect versions its releases and compatibility.
tags:
    - versioning
    - semver
---

# Versioning

## Understanding version numbers

Versions are composed of three parts: MAJOR.MINOR.PATCH. For example, the version 2.5.0 has a major version of 2, a minor version of 5, and patch version of 0.

Ocassionally, we will add a suffix to the version such as `rc`, `a`, or `b`. These indicate pre-release versions that users can opt-into installing to test functionality before it is ready for release.

Each release will increase one of the version numbers. If we increase a number other than the patch version, the versions to the right of it will be reset to zero.

## Prefect's versioning scheme

Prefect will increase the major version when significant and widespread changes are made to the core product. It is very unlikely that the major version will change without extensive warning.

Prefect will increase the minor version when:

- Introducing a new concept that changes how Prefect can be used
- Changing an existing concept in a way that fundementally alters how it is used
- Removing a deprecated feature

Prefect will increase the patch version when:

- Making enhancements to existing features
- Fixing behavior in existing features
- Adding new functionality to existing concepts
- Updating dependencies

## Breaking changes and deprecation

A breaking change means that your code will need to change to use a new version of Prefect. We strive to avoid breaking changes in all releases.

At times, Prefect will deprecate a feature. This means that a feature has been marked for removal in the future. When you use it, you may see warnings that it will be removed. A feature is deprecated when it will no longer be maintained. Frequently, a deprecated feature will have a new and improved alternative. Deprecated features will be retained for at least **3** minor version increases or **6 months**, whichever is longer. We may retain deprecated features longer than this time period.

Prefect will sometimes include changes to behavior to fix a bug. These changes are not categorized as breaking changes.

## Client compatibility with Orion

When running a Prefect Orion server, you are in charge of ensuring the version is compatible with those of the clients that are using the server. Prefect aims to maintain backwards compatibility with old clients for each server release. In contrast, sometimes new clients cannot be used with an old server. The new client may expect the server to support functionality that it does not yet include. For this reason, we recommend that all clients are the same version as the server or older.

For example, a client on 2.1.0 can be used with a server on 2.5.0. A client on 2.5.0 cannot be used with a server on 2.1.0.

## Client compatibility with Cloud

Prefect Cloud targets compatibility with all versions of Prefect clients. If you encounter a compatibility issue, please [file a bug report](https://github.com/prefectHQ/prefect/issues/new/choose).
