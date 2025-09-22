# Components Directory

This directory contains React components for the Prefect UI migration from Vue to React.

## Tech Stack
- React with TypeScript
- Tailwind CSS for styling
- shadcn/ui component library

## Component Guidelines

- ALWAYS check @prefect/ui-v2/src/components/ui before creating a new component
- ALWAYS create a Storybook story when creating a new component
- ALWAYS write tests when creating a new component
- Consider the current directory namespace when naming components to avoid duplication
- Prefer flat component structures over nested ones
- If creating nested components for readability, keep them in the same file as the parent component

## Forms

- Use `react-hook-form` for forms
- Use `zod` for form validation
- Use `zod-form-adapter` to convert `zod` schemas to `react-hook-form` form schemas
- Use `Form` component from `@/components/ui/form` to wrap forms
- Use `FormField` component from `@/components/ui/form` to wrap form fields
- Use `Stepper` component for wizard-like flows

## Organization

- Code, test, and storybook files should be contained in the same directory
- Include an `index.ts` file that exports components that are part of the "public API" of the directory

## Code Style

- NEVER use `document.querySelector` in components
- Use utilities from `lodash` for string manipulation
- NEVER use `React.FC`
- NEVER use `as unknown` or `eslint-disable` comments

## Testing

- Use `vitest` and `@testing-library/react` for testing
- API mocks are in @prefect/ui-v2/src/api/mocks
- All API calls should be mocked using `msw`
- NEVER skip tests