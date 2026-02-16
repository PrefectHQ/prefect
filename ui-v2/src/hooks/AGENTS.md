# Hooks Directory

This directory contains custom React hooks for general use patterns and common state management.

## Hook Guidelines

- Create hooks for common state patterns like debouncing user input, local storage, etc.
- Do NOT create mutation or query hooks here - those belong in the API directory
- Follow React hooks rules (use prefix, call at top level)
- Keep hooks focused and single-purpose

## Common Hook Patterns

- Debouncing user input
- Local storage interactions
- Window/viewport size tracking
- Form state management helpers
- Browser API abstractions (clipboard, notifications, etc.)
- Custom event handlers and listeners

## API Integration

- For queries: use `useSuspenseQuery` directly with query options factories from `src/api/`
- For mutations: create custom mutation hooks in the relevant `src/api/` subdirectory

## Organization

- Code, test, and related files should be in the same directory
- Export hooks through `index.ts` files