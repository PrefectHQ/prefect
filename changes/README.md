# Changelog Entries

This directory collects changelog entries between releases, to help avoid merge
conflicts in the changelog during development.

## Adding a new entry

Each PR should add a new file to this directory describing the relevant changes
in the PR. The file name doesn't matter as long as it is unique (we recommend
using the issue or PR number e.g. `issue1234.yaml` or `pr1234.yaml`).

To create a new change file:

- Create a new file in this directory. The file name doesn't matter as long as
  it is unique (we recommend using the issue or PR number e.g. `issue1234.yaml`
  or `pr1234.yaml`).

- Choose one (or more if a PR encompasses multiple changes) of the following headers:
    - `feature`
    - `enhancement`
    - `server`
    - `task`
    - `fix`
    - `deprecation`
    - `breaking` (for breaking changes)

- Fill in one (or more) bullet points under the heading, describing the change.
  Markdown syntax may be used. Each entry should consist of a brief description
  and a link to the relevant GitHub issue(s) or PR(s).

- If you would like to be credited as helping with this release, add a
  contributor section with your name and github username.

Here's an example of a PR that adds an enhancement

```yaml
enhancement:
  - "Example change description - [#1234](https://github.com/PrefectHQ/prefect/pull/1234)"

contributor:
  - "[Contributor Name](https://github.com/contributor_github_username)"
```

## Building the changelog

When creating a release, the changelog should built. This can be done using the
`update_changelog.py` script found in the repo root directory. This script will
collect all the change files and insert a new section into the `CHANGELOG.md`
file. The `changes/` directory will then be cleared to await the next release.

```shell
$ python update_changelog.py $RELEASE_VERSION_NUMBER --overwrite
```

To see the rendered changelog without updating the `CHANGELOG.md` file or
clearing the directory, omit the `--overwrite` flag. The rendered changelog
will then be sent to `stdout`.

```shell
$ python update_changelog.py $RELEASE_VERSION_NUMBER
```
