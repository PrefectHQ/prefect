# Prefect Documentation

Structural context for any agent working in `docs/`. For the full writing guide (page types, components, code testing, style), use the `/write-docs` skill.

## Platform

[Mintlify](https://mintlify.com/) docs published to [docs.prefect.io](https://docs.prefect.io). All files use `.mdx` (Markdown + JSX). Site config lives in `docs/docs.json`.

## Directory structure

```
docs/
  v3/                     # Primary docs for Prefect 3.x
    get-started/          # Installation, quickstart
    concepts/             # Core concepts (flows, tasks, states, deployments, etc.)
    how-to-guides/        # Practical guides organized by category
    advanced/             # Advanced topics
    examples/             # Auto-generated from examples/ Python files — do NOT edit directly
    api-ref/              # Auto-generated API reference — do NOT edit directly
      python/             # SDK reference
      cli/                # CLI command reference
      rest-api/           # REST API docs (server/ and cloud/)
    release-notes/        # Version release notes
    img/                  # Images organized by section
  integrations/           # Integration-specific docs (prefect-aws, prefect-gcp, etc.)
    catalog/              # YAML metadata for each integration
  contribute/             # Contributor guides
  snippets/               # Reusable MDX snippets imported across pages
  images/                 # Legacy images
  logos/                  # Brand assets
  styles/                 # Vale linting styles
```

## Auto-generated content — do not edit

- `v3/examples/` — generated from top-level `examples/` Python files by `generate_example_pages.py`
- `v3/api-ref/` — generated API reference (Python SDK, CLI, REST API)

## File format

Every `.mdx` file starts with YAML frontmatter:

```yaml
---
title: Page Title
description: Brief description for SEO and navigation
sidebarTitle: Optional shorter sidebar label   # optional
icon: icon-name                                # optional, Mintlify icon
mode: wide                                     # optional
keywords: ["keyword1", "keyword2"]             # optional, for search
---
```

Frontmatter keys are always lowercase. The `title` renders as the page's H1, so start body content at `##` — do not add another H1.

## Navigation

All pages must be registered in `docs/docs.json` under `navigation.tabs`. When adding a page, add its path (without `.mdx` extension) to the appropriate group.

## Links

Use absolute paths from the docs root without `.mdx`:

```mdx
See the [flows documentation](/v3/concepts/flows) for details.
```

Do not use relative paths or include `.mdx` in links.

## Redirects

When renaming or moving a page, add a redirect in `docs/docs.json` `redirects` array so existing links continue to work. Never remove existing redirects unless you are certain the old URL has no inbound traffic. Paths should not include `.mdx`.

## Terminology and casing

Preferred terms are enforced by Vale via `docs/styles/CustomStyles/WordList.yml`. Key entries:

- "Prefect Cloud" (not "Prefect cloud")
- "Prefect server" (not "Prefect Server")
- "infrastructure" (not "infra")
- "Kubernetes" (not "k8s")
- "open source" (not "open-source")

## Versioning

All new content goes in `docs/v3/`. Do not create pages outside `v3/` for current Prefect 3.x features.

## Local development

```bash
just docs     # Start the dev server at localhost:3000
just links    # Check for broken links
just lint     # Run Vale linter
```

## Key rules

1. **Do not edit auto-generated files.** Pages under `v3/examples/` and `v3/api-ref/` are generated from source code.
2. **Register new pages in `docs/docs.json`.** An unregistered page won't appear in navigation.
3. **Use `.mdx` extension** for all new documentation files.
4. **Use Mintlify components** (`<Note>`, `<Tabs>`, `<Steps>`, etc.) rather than Markdown-native admonition syntax.
5. **Keep code examples working.** They are tested in CI. Use `{/* pmd-metadata: notest */}` only when a block genuinely cannot be tested.
6. **Use absolute link paths** without file extensions (e.g., `/v3/concepts/flows`).
7. **Check for existing snippets** in `snippets/` before duplicating content.
8. **Start body content at `##`.** The frontmatter `title` renders as H1; do not add another H1 in the body.