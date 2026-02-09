# Agents Guide for Prefect Documentation

This file guides AI agents when creating and updating documentation in this directory.

## Platform

The docs use [Mintlify](https://mintlify.com/) and are published to [docs.prefect.io](https://docs.prefect.io). All documentation files use the `.mdx` extension (Markdown with JSX support). The site configuration lives in `docs/docs.json`.

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

## Page types

Each section of the docs serves a distinct purpose. Place new content in the right section and match its tone and structure.

### Get Started (`v3/get-started/`)

Onboarding pages for new users. Content should be linear, opinionated, and get the reader to a working result as fast as possible. Use `<Steps>` for sequential instructions and `<Tabs>` to offer Cloud vs. self-hosted paths. Minimize explanation — link to Concepts for deeper understanding.

### Concepts (`v3/concepts/`)

Explain **what** something is and **why** it matters. Concepts pages define Prefect's mental model — flows, tasks, states, deployments, events, work pools, etc. Start with a short code example showing the concept in action, then explain the underlying model, lifecycle, and relationships to other concepts. Link to How-to Guides for step-by-step instructions. Do not provide exhaustive procedural walkthroughs here.

### How-to Guides (`v3/how-to-guides/`)

Task-oriented pages that show **how** to accomplish a specific goal. Each page should solve one problem (e.g., "How to write and run a workflow", "How to set up retries"). Structure as a series of actionable steps with code examples. Meet the reader where they are — do not assume familiarity with Prefect internals. Use the smallest amount of Prefect-specific jargon possible, and explain or link terms when they are unavoidable.

Guides are organized into the following categories:

- **`workflows/`** — Writing, running, and customizing flows and tasks: retries, caching, concurrency, logging, testing, runtime info, state hooks, and artifacts.
- **`deployments/`** — Creating, scheduling, running, and versioning deployments, including `prefect.yaml` configuration and flow code storage.
- **`deployment_infra/`** — Running workflows on specific infrastructure: Docker, Kubernetes, serverless platforms (AWS ECS, Azure ACI, GCP Cloud Run), Modal, Coiled, Prefect Managed, and local processes. Also covers work pool management.
- **`automations/`** — Setting up event-driven automations: creating automations and triggers, chaining deployments via events, custom notifications, and accessing event payloads in flows.
- **`cloud/`** — Prefect Cloud-specific operations: connecting to Cloud, managing workspaces and users, creating webhooks, and troubleshooting.
- **`configuration/`** — Configuring the Prefect environment: managing settings, storing secrets, and using variables.
- **`ai/`** — Using Prefect with AI tooling, such as the Prefect MCP server.
- **`migrate/`** — Upgrading from older Prefect versions or migrating from other tools like Airflow.
- **`self-hosted/`** — Running the Prefect server yourself via Docker Compose, the CLI, or on Windows.

### Advanced (`v3/advanced/`)

In-depth pages for experienced users covering topics like transactions, interactive workflows, infrastructure-as-code, scaling self-hosted deployments, and custom API integrations. These assume familiarity with core concepts and how-to patterns. They can be longer and more detailed than how-to guides.

### Examples (`v3/examples/`)

**Auto-generated — do not edit directly.** Each page is generated from a standalone Python file in the repo's top-level `examples/` directory by `generate_example_pages.py`. To add an example, create a new `.py` file in `examples/` with YAML frontmatter in comments and run `just generate-examples`. See `contribute/docs-contribute.mdx` for the full process.

### Integrations (`integrations/`)

Each integration (e.g., `prefect-aws`, `prefect-gcp`) has its own subdirectory. The `index.mdx` covers installation, credential setup (blocks), and key capabilities. Additional pages cover specific workers, tasks, or SDK reference. Integration metadata lives in `integrations/catalog/` as YAML files. Follow the existing pattern: "Why use it" section, prerequisites, install instructions, blocks setup, then per-service usage sections.

### API Reference (`v3/api-ref/`)

**Auto-generated — do not edit directly.** Covers the Python SDK (`python/`), CLI commands (`cli/`), and REST API (`rest-api/`). CLI pages use `<ResponseField>` and `<Accordion>` components for arguments and options.

### Release Notes (`v3/release-notes/`)

Changelogs organized by product surface: `oss/` for open-source releases, `cloud/` for Prefect Cloud, `integrations/` for integration packages.

### Contribute (`contribute/`)

Guides for contributors: how to set up the dev environment, write docs, develop integrations, and follow code style conventions.

## Adding vs. updating content

### When to update an existing page vs. create a new one

- **Update an existing page** when the new content is a variation, option, or closely related technique for something the page already covers. For example, a new retry strategy belongs on the existing retries page, not a new page.
- **Create a new page** when the content addresses a distinct goal that doesn't fit naturally into any existing page. A good test: if the page title would need to become vague or a compound sentence to accommodate the new content, it deserves its own page.
- When in doubt, prefer extending an existing page. Fewer, more comprehensive pages are easier for readers to discover than many small, fragmented ones.

### When to add a new category or section

- **Create a new subdirectory** only when you have multiple pages (or a clear roadmap for multiple pages) that share a theme not covered by any existing category. A single page does not justify a new category — place it in the closest existing one.
- Before creating a category, check whether the content fits in an existing one. For example, a guide about running flows on a new cloud platform belongs in `deployment_infra/`, not a new category named after that platform.
- New categories must also be added as a group in the `navigation.tabs` section of `docs/docs.json`, with an `index.mdx` page for the group overview.

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

Frontmatter keys are always lowercase (e.g., `title`, `description`, not `Title`, `Description`). After frontmatter, write standard Markdown with Mintlify JSX components as needed. The `title` in frontmatter renders as the page's H1, so start body content at `##` and do not add another H1.

## Mintlify components

Use these components (not standard Markdown admonition syntax):

```mdx
<Note>Important information.</Note>
<Warning>Caution about potential issues.</Warning>
<Tip>Helpful suggestion.</Tip>
<Info>Additional context.</Info>

<Accordion title="Expandable section">
  Content hidden until clicked.
</Accordion>

<Tabs>
  <Tab title="Option A">Content for A</Tab>
  <Tab title="Option B">Content for B</Tab>
</Tabs>

<Steps>
  <Step title="First step">Instructions</Step>
  <Step title="Second step">Instructions</Step>
</Steps>

<CardGroup cols={3}>
  <Card title="Title" icon="icon" href="/v3/path">
    Description text.
  </Card>
</CardGroup>

<CodeGroup>
```bash pip
pip install prefect
```
```bash uv
uv pip install prefect
```
</CodeGroup>
```

## Reusable snippets

Snippets live in `snippets/` and are imported with JSX:

```mdx
import ComponentName from '/snippets/path.mdx'

<ComponentName />
```

Always check for an existing snippet before writing duplicate content. Key snippets to know about:

- `snippets/installation.mdx` — Standard Prefect install instructions (used in `v3/get-started/install.mdx`). Use this instead of writing ad-hoc install blocks.
- `snippets/resource-management/` — Consistent "manage this resource via CLI / API / Terraform / Helm" callouts. Import the relevant variant when documenting a Prefect resource.

## Code blocks

Code blocks support language hints, filenames, line highlighting, and expandable sections:

````mdx
```python my_flow.py
from prefect import flow

@flow
def hello():
    print("Hello!")
```

```bash {3} [expandable]
prefect deploy --all
prefect work-pool create my-pool --type process
prefect worker start --pool my-pool
```
````

Mark code blocks that should **not** be tested with the comment `{/* pmd-metadata: notest */}` on the line before the code block.

Prefer minimal, runnable snippets that produce a visible result (printed output, a return value, or a logged message). Avoid placeholder names like `foo`/`bar` in user-facing examples — use realistic names that reflect the domain (e.g., `process_order`, `customer_id`).

## Navigation

All pages must be registered in `docs/docs.json` under the `navigation.tabs` array, otherwise they won't appear in the site. When adding a new page, add its path (without `.mdx` extension) to the appropriate group in `docs/docs.json`.

## Links

Use absolute paths from the docs root without the `.mdx` extension:

```mdx
See the [flows documentation](/v3/concepts/flows) for details.
```

Do not use relative paths or include `.mdx` in links.

## Redirects

When renaming or moving a page, add a redirect in the `redirects` array in `docs/docs.json` so existing links and bookmarks continue to work. Each entry maps a `source` (old path) to a `destination` (new path):

```json
{
  "source": "/v3/old/path",
  "destination": "/v3/new/path"
}
```

Redirects support wildcard slugs with `:slug*` for moving entire sections:

```json
{
  "source": "/old-section/:slug*",
  "destination": "/v3/new-section/:slug*"
}
```

Rules:
- **Always add a redirect when moving or renaming a page.** External sites, bookmarks, and search engines link to existing URLs.
- **Never remove existing redirects** unless you are certain the old URL has no inbound traffic.
- Keep entries sorted logically — wildcarded section redirects first, then specific page redirects.
- Paths should not include the `.mdx` extension.
- The `errors.404.redirect` setting in `docs/docs.json` is enabled, which automatically attempts to resolve 404s, but explicit redirects are still required for known moves.

## Images

Place images in `v3/img/` organized by section (e.g., `v3/img/ui/`, `v3/img/concepts/`). Reference them with absolute paths:

```mdx
![Description](/v3/img/ui/screenshot.png)
```

- Always include meaningful alt text that describes what the image shows.
- Use compressed PNG or WebP format to keep page load times fast.
- Avoid committing unnecessarily large screenshots; crop to the relevant area.

## Linting

Docs are linted with [Vale](https://vale.sh/) using Google style, Vale defaults, and custom Prefect rules. Run locally:

```bash
just lint
```

Or manually: `vale --glob='**/*.{md,mdx}' .`

## Code example testing

Python code blocks in `.mdx` files are automatically extracted and executed as tests using [pytest-markdown-docs](https://github.com/modal-labs/pytest-markdown-docs). Tests run in CI against a live Prefect server and are parallelized with pytest-xdist (up to 6 workers). All test configuration — fixtures, skip lists, and injected globals — lives in `docs/conftest.py`.

### How it works

By default, every fenced Python code block in an `.mdx` file is treated as an independent test. The plugin extracts the block, executes it, and fails if it raises an exception. Each block runs in its own namespace unless `continuation` is used (see below).

### Running tests locally

There is no `just` command for markdown tests. Run them manually:

```bash
# Start a Prefect server in the background
PREFECT_HOME=$(pwd) uv run prefect server start &

# Run the markdown doc tests
PREFECT_API_URL="http://127.0.0.1:4200/api" uv run pytest docs/ --markdown-docs -m markdown-docs
```

### pmd-metadata directives

Control test behavior with `{/* pmd-metadata: <directive> */}` comments placed on the line immediately before a code fence.

**`notest`** — Skip this code block entirely. Use when code is illustrative, incomplete, or requires setup that cannot be provided in the test environment.

```mdx
{/* pmd-metadata: notest */}
```python
# This block will not be tested
prefect deploy --some-hypothetical-flag
```
```

**`continuation`** — Share state (imports, variables, function definitions) from preceding code blocks on the same page. Without this, each block starts with a clean namespace. Use when a multi-step example is split across blocks for readability.

```mdx
```python
from prefect import flow

@flow
def my_workflow() -> str:
    return "Hello, world!"
```

{/* pmd-metadata: continuation */}
```python
my_workflow()  # Can reference the function defined above
```
```

**`fixture:<name>`** — Inject a pytest fixture defined in `conftest.py` as a global in the code block. Use when a block needs mocking (e.g., HTTP calls).

```mdx
{/* pmd-metadata: fixture:mock_post_200 */}
```python
import requests
response = requests.post(endpoint, headers=headers, json=data)
assert response.status_code == 200
```
```

### Global imports

The `pytest_markdown_docs_globals` hook in `conftest.py` injects a small set of globals into every code block automatically: `Mapped`, `Run`, `Union`, `mapped_column`, `sa`. You do not need to import these in doc examples.

### Autouse fixtures

Two fixtures are applied to every test automatically (defined in `conftest.py`):

- `mock_runner_start` — Mocks `prefect.cli.flow.Runner.start` so flow-serving examples don't actually start a long-running process.
- `mock_base_worker_submit` — Mocks `BaseWorker.submit` and `KubernetesWorker.submit` so worker examples don't attempt real infrastructure calls.

### Skipped files

Some files are skipped entirely via the `SKIP_FILES` dict in `conftest.py`. Common reasons include needing database fixtures, block cleanup, live network calls, or async contexts. Additionally:

- All files under `v3/api-ref/python/` are auto-skipped (generated reference docs).
- All files under `v3/examples/` are auto-skipped (tested separately in their source repo).

When adding a new page that genuinely cannot be tested, add it to `SKIP_FILES` with a reason rather than marking every block with `notest`.

## Local development

```bash
just docs     # Start the dev server at localhost:3000
just links    # Check for broken links
just lint     # Run Vale linter
```

Requires Node.js and npx. See `contribute/docs-contribute.mdx` for full setup instructions.

## Tone and style

- Use second person ("you") and active voice in present tense.
- Avoid first person ("I", "we") and marketing language ("powerful", "seamless", "best-in-class").
- Be direct and concise. Shorter sentences are easier to scan.
- Follow the [Google developer documentation style guide](https://developers.google.com/style) as the baseline.

## Terminology and casing

Preferred terms and casing are enforced by Vale via `docs/styles/CustomStyles/WordList.yml`. Check that file before introducing product names or abbreviations. Key Prefect-specific entries:

- "Prefect Cloud" (not "Prefect cloud")
- "Prefect server" (not "Prefect Server")
- "infrastructure" (not "infra")
- "Kubernetes" (not "k8s")
- "open source" (not "open-source")

## Versioning

All new content should go in `docs/v3/` unless you are explicitly documenting a legacy version. Do not create pages outside of `v3/` for current Prefect 3.x features. Legacy pages (if any remain) should not be updated with v3 content — link to the v3 equivalent instead.

## Doc quality checklist

Before considering a page complete, verify:

1. The page opens with appropriate context: for how-to guides, a single-sentence scope line (or jump straight into steps if the title already establishes the goal); for concepts and advanced pages, an opening paragraph that defines the topic and why it matters.
2. Prerequisites (tools, access, prior knowledge) are called out up front.
3. The page includes at least one cross-link to a related Concept or How-to page.
4. All code blocks are runnable and tested, or explicitly marked with `{/* pmd-metadata: notest */}` with a reason.
5. The page is registered in `docs/docs.json` navigation.

## Key rules

1. **Do not edit auto-generated files.** Pages under `v3/examples/` and `v3/api-ref/` are generated from source code.
2. **Register new pages in `docs/docs.json`.** An unregistered page won't appear in navigation.
3. **Use `.mdx` extension** for all new documentation files.
4. **Use Mintlify components** (`<Note>`, `<Tabs>`, `<Steps>`, etc.) rather than Markdown-native admonition syntax.
5. **Keep code examples working.** They are tested in CI. Use `{/* pmd-metadata: notest */}` only when a block genuinely cannot be tested.
6. **Use absolute link paths** without file extensions (e.g., `/v3/concepts/flows`).
7. **Check for existing snippets** in `snippets/` before duplicating content.
8. **Start body content at `##`.** The frontmatter `title` renders as H1; do not add another H1 in the body.
