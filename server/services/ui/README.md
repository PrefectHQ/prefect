# Prefect Server UI

## Project setup

Download `nvm` from [here](https://github.com/creationix/nvm#installation). `nvm` is a tool this project uses to manage node versions. When you're finished installing, run:

```bash
nvm install
nvm use
```

at the root of this project directory. `nvm` will begin using the version of node specified in this project's `.nvmrc` file. Once you're using the correct version of node, you can:

```bash
npm install
```

### VueCLI3

This project was created with [VueCLI3](https://cli.vuejs.org/guide/). As such, it can sometimes be useful to install the cli. To do this:

```bash
# You'll install the CLI globally for a particular node version in nvm
npm i -g @vue/cli
```

In particular, you'll need this if you want to install a VueCLI plugin. [See here](https://cli.vuejs.org/guide/plugins-and-presets.html). As a reminder, plugins should be installed as dev dependencies.

```bash
# with the VueCLI globally installed
npm i --save-dev vue-cli-plugin-something-or-other
vue add vue-cli-plugin-something-or-other
```

### Local Development

This command will start webpack dev server and make the UI accessible http://localhost:8080.

```bash
npm run serve
```

### Testing

```bash
npm run test:unit
```

If you'd like to see a testing coverage report, run:

```bash
npm run test:coverage
```

To update snapshot tests, run:

```bash
npm run test:snapshots
```

To only run tests related to changed files as detected by git, run:

```bash
npm run test:unit -- -o
```

### Lints SCSS files and code within `<style></style>` tags in vue files

```bash
npm run lint:css
```

### Lints and fixes files

```bash
npm run lint
```
