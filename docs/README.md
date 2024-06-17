# Prefect Documentation Source

Mintlify is used to host and build the documentation.

This repository builds the Prefect 3.0rc docs at [docs-3.prefect.io](https://docs-3.prefect.io) temporarily.
2.x docs are still hosted at [docs.prefect.io](https://docs.prefect.io), although they are being ported to Mintlify.

## Getting started

Make sure you have a recent version of Node.js installed. We recommend using [nvm](https://github.com/nvm-sh/nvm) to manage Node.js versions.

1. Clone this repository.
2. Run `nvm use node` to use the correct Node.js version.
3. Run `npm i -g mintlify` to install Mintlify.
4. Run `mintlify dev` to start the development server.

Your docs should now be available at `http://localhost:3000`.

See the [Mintlify documentation](https://mintlify.com/docs/development) for more information on how install Mintlify, build previews, and use Mintlify's features while writing docs.

`.mdx` files are Markdown files that can contain JavaScript and React components. They are used to create interactive documentation.
