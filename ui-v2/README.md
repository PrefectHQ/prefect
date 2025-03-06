# Prefect UI

## Project setup

```
npm ci
```

### Compiles and hot-reloads for development

```
npm run dev
```

### Compiles and minifies for production

```
npm run build
```

### Lints and fixes files

```
npm run lint
```
This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
export default tseslint.config({
  languageOptions: {
    // other options...
    parserOptions: {
      project: ['./tsconfig.node.json', './tsconfig.app.json'],
      tsconfigRootDir: import.meta.dirname,
    },
  },
})
```

- Replace `tseslint.configs.recommended` to `tseslint.configs.recommendedTypeChecked` or `tseslint.configs.strictTypeChecked`
- Optionally add `...tseslint.configs.stylisticTypeChecked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and update the config:

```js
// eslint.config.js
import react from 'eslint-plugin-react'

export default tseslint.config({
  // Set the react version
  settings: { react: { version: '18.3' } },
  plugins: {
    // Add the react plugin
    react,
  },
  rules: {
    // other rules...
    // Enable its recommended rules
    ...react.configs.recommended.rules,
    ...react.configs['jsx-runtime'].rules,
  },
})
```

### Storybook

Storybook is integrated into this project for component development and documentation. To start Storybook:

```
npm run storybook
```

This will launch Storybook locally at http://localhost:6006 (if something is already running on this port the command may fail).

#### Creating a new story

Stories are created alongside their components. To add a new story:

1. Create a new file named `[ComponentName].stories.ts` or `[ComponentName].stories.tsx` in the same directory as your component.
2. Follow this basic structure:

```tsx
import type { Meta, StoryObj } from '@storybook/react';
import YourComponent from './YourComponent';

const meta: Meta<typeof YourComponent> = {
  title: 'Components/YourComponent',
  component: YourComponent,
  parameters: {
    // Optional parameters
  },
  argTypes: {
    // Control the props exposed in Storybook UI
  },
};

export default meta;
type Story = StoryObj<typeof YourComponent>;

// Define your stories
export const Default: Story = {
  args: {
    // Component props for this story
  },
};

export const AnotherVariant: Story = {
  args: {
    // Different component props for another variant
  },
};
```

#### Writing effective stories

- **Use args**: Define component props using the `args` property for each story
- **Create variants**: Make multiple stories to showcase different states of your component
- **Document props**: Add descriptions to your props using argTypes
- **Use decorators**: Wrap your components in decorators to provide context where needed
- **Add controls**: Enable Storybook controls to let users interact with your component

This project uses a custom theme configured in `.storybook/prefect-theme.ts` and global decorators set up in `.storybook/preview.ts`.

#### Building Storybook for deployment

To build a static version of Storybook for deployment:

```
npm run build-storybook
```

This will generate a static Storybook site in the `storybook-static` directory.

