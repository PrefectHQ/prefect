# Storybook Directory

This directory contains Storybook utilities and decorators.

## Storybook Guidelines

- Use `fn` from `storybook/test` for callback functions
- When mocking with `msw`, use `buildApiUrl` from `@tests/utils/handlers` to build URLs
- Decorators for stories are available in `@prefect/ui-v2/src/storybook/utils`
- Use decorators for components that rely on `queryClient` and `router` objects

## Required Decorators

Components may need these decorators based on their dependencies:
- Query client decorator for components using Tanstack Query
- Router decorator for components using Tanstack Router
- Theme decorator for components using Tailwind/shadcn styling

## Story Creation

- ALWAYS create a Storybook story when creating a new component
- Structure stories to showcase different component states
- Use mock data from `@prefect/ui-v2/src/mocks` for realistic examples