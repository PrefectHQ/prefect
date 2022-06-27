# Documentation

Documentation is incredibly important to Prefect, both for explaining its concepts to general audiences and describing its API to developers.

## Docstrings

Prefect auto-generates API documentation from docstrings by compiling them to
Markdown. For details on properly formatting your docstrings, please see the
[code style](./style.md#docstrings) guide.

## API Reference

Modules, functions, and classes must be explicitly added to the auto-generated
documentation. First, update the `docs/outline.toml` file with the following
information: 

- a TOML header with the path to the generated Markdown file (e.g. `pages.utilities.example`)
- `title` (str): the title of the generated docs page
- `module` (str, optional): the import path to the module being documented. The
  module docstring will be displayed at the top of the page.
- `classes` (list or dict, optional): a list of class names in `module` to
  document (all public methods of these classes will be documented).
  Alternatively, a dict mapping class names to lists of method names to
  document can be used (only explicitly listed method names will be
  documented).
- `functions` (list, optional): a list of function names in `module` to document

For example, to document a module `prefect.utilities.example` with a class
`MyClass` and a function `my_function`, you might add the following to
`outline.toml`:

```
[pages.utilities.example]
title = "Example Module"
module = "prefect.utilities.example"
classes = ["MyClass"]
functions = ["my_function"]
```

Most reference docs sections update their sidebars automatically by detecting
the files generated from `outline.toml`. However, in some instances you may
have to include your file explicitly. To do so, update
`docs/.vuepress/config.js` and add it to the appropriate "children" section.
The actual `prefect.utilities` section _does_ auto-update its sidebar, but for
the sake of example, you would add the new file to the children array like so:

```javascript
{
    title: 'prefect.utilities',
    collapsable: true,
    children: [
        'utilities/collections',
        'utilities/example',  // our new file
        ...
    ]
}
```

### Archiving API docs

Whenever a new minor release of Prefect is cut, we must archive the old API docs so they are available for users using the older versions. For example, this means that if we are releasing Prefect `0.10.0` then the highest patch release of `0.9.x` must be archived. To do so, follow these steps:

- first, make sure you are on the release commit: `git checkout $VERSION_TAG`
- next, generate the documentation: `cd docs/ && python generate_docs.py`
- push the API docs into a new folder: `cd api/ && mv latest/ $VERSION_TAG`
- begin tracking any changes to the new folder: `git checkout master && git checkout -b new-version-branch && git add $VERSION_TAG`
- lastly, create a new `sidebar.js` file in the `$VERSION_TAG/` folder with an exportable sidebar object (see [0.11.5](https://github.com/PrefectHQ/prefect/blob/master/docs/api/0.11.5/sidebar.js) for an example)
- this sidebar will need to be imported into `docs/.vuepress/config.js` and added to a new dropdown option in the API navigation bar

The most recent release of Prefect will always be the `latest` release and the API docs for latest are auto generated with each doc build. On release the `Latest (x.y.z)` should be updated with the most recent version in [`docs/.vuepress/config.js`](https://github.com/PrefectHQ/prefect/blob/master/docs/.vuepress/config.js).

## Concepts

Prefect also includes a great deal of "concept" documentation, which covers features, tutorials, guides, and examples separately from the auto-generated API reference. This page is part of the concept documentation for development! We refer to non-API documentation as Prefect's "Guide".

To write concept docs, add Markdown files to the `docs/guide` directory (or one of its subdirectories). To ensure that your page is displayed in the navigation, edit `docs/.vuepress/config.js` to include a reference to it.

## Semantics

### Capitalization

Concepts that refer to proper nouns or are trademarked should always be capitalized, including "Prefect", "Core" (when referring to Prefect Core), and "Cloud" (when referring to Prefect Cloud).

Other Prefect terms, like "flow" or "task", should generally not be capitalized unless they refer to a specific Python class. For example:

> When a flow is run, its tasks are executed in sequence. Each `Task` has a `trigger` function that determines if it should run.
>
> To execute a `Flow`, call its `.run()` method.
>
> In order to manage data serialization, users can specify one or more `ResultHandlers` for their flows and tasks.
>
> Prefect uses a rich state system to communicate information between tasks. Each `State` has multiple attributes, including an informative message. 

## Previewing docs locally

Documentation (including both concepts and API references) is built and deployed with every merge to Prefect's master branch. Prior to merge, a GitHub check will allow you to see a hosted version of the documentation associated with every PR.

To preview docs locally, you'll first need to install
[VuePress](https://vuepress.vuejs.org/) and its dependencies. This requires
[Node.js](https://nodejs.org/en/) and `npm` (which is installed with Node.js).
You will also need to install the rest of Prefect's dependencies for generating
docs. You only need to do this once:

```bash
git clone https://github.com/PrefectHQ/prefect.git
cd prefect
npm install
pip install ".[all_extras]"
```

To launch a documentation preview:

```bash
cd prefect
npm run docs:dev
```

You'll see a status update as the docs build, and then an announcement that they are available on `http://localhost:8080`.

!!! tip Hot-reloading docs
  Concept docs will hot-reload every time you save a file, but API reference docs must be regenerated by restarting the server.
:::
