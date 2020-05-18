# Contributing

## Documentation

Contributing to Prefect's docs is just as important as adding new code! We welcome your help, whether fixing a simple typo or writing a new tutorial. For new users, this can be an excellent way to get involved.

## Contribution checklist

### Commit formatting

When possible, try to craft useful commits. Each commit should be logically distinct and self-contained, which makes reviewing code easier and understanding _why_ changes were made easier.

We recommend following [Chris Beam's style guide](https://chris.beams.io/posts/git-commit/), which has 7 rules for effective commit messages:

1. Separate subject from body with a blank line
1. Limit the subject line to 50 characters
1. Capitalize the subject line
1. Do not end the subject line with a period
1. Use the imperative mood in the subject line
1. Wrap the body at 72 characters
1. Use the body to explain what and why vs. how

### Changelog

It's important to update Prefect's [changelog](/api/latest/changelog.html) with
any adjustments to the project. Each release has a few sections:

- Features: headline additions to the system
- Enhancements: improvements to existing functionality, or minor additions
- Server: improvements to Prefect Server
- Task Library: additions to Prefect's task library
- Fixes: adjustments that fix bugs or other conditions
- Deprecations: any deprecated functionality
- Breaking Changes: any changes that break Prefect's backwards-compatibility

To avoid merge conflicts, Prefect tracks changelog entries as separate files in
the `changes/` directory. To add a new entry:

1. Create a new file in the `changes/` directory. The file name doesn't matter
   as long as it is unique (we recommend using the issue or PR number e.g.
   `issue1234.yaml` or `pr1234.yaml`).

2. Choose one (or more if a PR encompasses multiple changes) of the following
   headers:
    - `feature`
    - `enhancement`
    - `server`
    - `task`
    - `fix`
    - `deprecation`
    - `breaking`

3. Fill in one (or more) bullet points under the heading, describing the
   change. Markdown syntax may be used. Each entry should consist of a brief
   description and a link to the relevant GitHub issue(s) or PR(s).

4. If you would like to be credited as helping with this release, add a
   contributor section with your name and github username.

Here's an example of a PR that adds an enhancement

```yaml
enhancement:
  - "Add new `TimedOut` state for task execution timeouts - [#255](https://github.com/PrefectHQ/prefect/issues/255)"

contributor:
  - "[Chris White](https://github.com/cicdw)"
```

### Tests

Make sure that any new functionality is well tested! See the [tests](../development/tests.html) guide for more.

### Opening a PR

A helpful PR explains WHAT changed and WHY the change is important. Please take time to make your PR descriptions as helpful as possible -- both for code review today and information in the future.
