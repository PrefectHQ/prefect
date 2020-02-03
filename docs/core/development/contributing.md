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

It's important to update Prefect's [changelog](/api/latest/changelog.html) with any adjustments to the project. Each release has four sections:

- Features: headline additions to the system
- Enhancements: improvements to existing functionality, or minor additions
- Task Library: additions to Prefect's task library
- Fixes: adjustments that fix bugs or other conditions
- Breaking Changes: any changes that break Prefect's backwards-compatibility

Each entry consists of a brief description and a link to the relevant GitHub issue(s) or PR(s). For example:

```
### Enhancements

- Add new `TimedOut` state for task execution timeouts - [#255](https://github.com/PrefectHQ/prefect/issues/255)
- Use timezone-aware dates throughout Prefect - [#325](https://github.com/PrefectHQ/prefect/pull/325)
- Add `description` and `tags` arguments to `Parameters` - [#318](https://github.com/PrefectHQ/prefect/pull/318)
```

### Tests

Make sure that any new functionality is well tested! See the [tests](../development/tests.html) guide for more.

### Opening a PR

A helpful PR explains WHAT changed and WHY the change is important. Please take time to make your PR descriptions as helpful as possible -- both for code review today and information in the future.
