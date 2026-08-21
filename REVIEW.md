# Code review guidance

Repo-specific guidance for human and automated reviewers of Prefect. Implementation standards
and component contracts belong in the applicable `AGENTS.md` files; do not duplicate them here.

## Review axes

Review every diff along two independent axes:

- **Standards** — does the change follow the applicable repository instructions?
- **Spec** — does the change faithfully implement the originating issue or specification?

Prefix findings with `[Standards]` or `[Spec]`. Do not merge or rank findings across axes, and
do not let success on one axis hide problems on the other.

## Standards review

Read every `AGENTS.md` and `REVIEW.md` whose scope contains a changed file, plus the relevant
contribution guides under `docs/contribute/`. Follow references to paired implementations,
owning components, architectural boundaries, and other contracts material to the diff. Verify
those contracts against their implementations rather than reasoning from names or mocks alone.

Cite the instruction file and rule for every hard Standards finding. Repository instructions
override the following Fowler code-smell baseline, which is always a judgement call:

- Mysterious Name
- Duplicated Code
- Feature Envy
- Data Clumps
- Primitive Obsession
- Repeated Switches
- Shotgun Surgery
- Divergent Change
- Speculative Generality
- Message Chains
- Middle Man
- Refused Bequest

Skip formatting, lint, and other failures that automated tooling reliably identifies unless
they expose a broader behavioral problem.

## Spec review

Find the authoritative specification in this order:

1. A linked GitHub issue and its maintainer decisions, including issue references in commits
2. A specification explicitly linked from the issue or pull request
3. A relevant document under `docs/`, `plans/`, or another specification directory
4. The pull request description as supplemental context

For each Spec finding, cite the requirement it relies on. Report requirements that are missing
or partial, behavior that was not requested, and implementations that appear to satisfy a
requirement but do so incorrectly. If no authoritative specification is available, report that
the Spec axis could not be evaluated instead of inventing requirements.

## Reporting discipline

- Review the diff against its merge base; do not turn adjacent pre-existing problems into
  findings.
- Quote the relevant changed code and cite the governing standard or requirement.
- Distinguish observed failures from inferred risks and state what evidence would confirm an
  inference.
- Avoid speculative cleanup and preference-only findings.
