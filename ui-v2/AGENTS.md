# Prefect UI v2 - React Migration

This is the new React-based Prefect UI, migrating from the legacy Vue application with minimal visual and functional changes.

## Project Structure

```
prefect/ui-v2/
├── src/
│   ├── api/           # API queries, mutations, and mocks
│   ├── components/    # React components organized by domain
│   ├── hooks/         # Custom hooks for common patterns
│   ├── lib/           # Utility functions and shared code
│   ├── mocks/         # Mock data factories
│   ├── routes/        # Tanstack Router route definitions
│   ├── storybook/     # Storybook utilities and decorators
│   └── utils/         # Helper functions and utilities
├── tests/             # Test utilities and configuration
├── .storybook/        # Storybook configuration
└── public/            # Static assets
```

## Tech Stack

- **React** with TypeScript
- **Tailwind CSS** - styling
- **shadcn/ui** - UI component library
- **Tanstack Query** - API state management
- **Tanstack Router** - routing
- **Tanstack Table** - table state management
- **react-hook-form** - form state management
- **Recharts** - charts and data visualization
- **Vitest** - testing framework
- **Storybook** - component development and documentation
- **MSW** - API mocking

## Development Workflow

### Development Process

1. **Start development server**: `npm run dev` (runs on http://localhost:5173/)
2. **Write tests first** for new components and hooks before implementation
3. **Implement** the component/hook following existing patterns
4. **Create Storybook story** to document component variants
5. **Verify functionality** in the browser at http://localhost:5173/
6. **Compare with legacy Vue** implementation at http://localhost:4200/ for consistency

### Pre-commit Checklist

Before committing any changes, always run:

1. **Format and lint**: `npm run check` (Biome formatting and linting)
2. **Additional linting**: `npm run lint` (ESLint rules)
3. **Build verification**: `npm run build` (ensure no build errors)
4. **Test verification**: `npm test` (run relevant tests)

### Performance Tips

- Run **single tests** for faster feedback: `npm test -- ComponentName`
- Run **lint on single files** for performance: `npx eslint src/path/to/file.ts --fix`
- Use **Storybook** for isolated component development: `npm run storybook`

### Browser Testing

- **Primary development**: http://localhost:5173/
- **Legacy comparison**: http://localhost:4200/
- **Component documentation**: http://localhost:6006/ (Storybook)

## Common Commands

- `npm run dev` - Start development server
- `npm run build` - Build production bundle
- `npm run test` - Run tests
- `npm run check` - Run linter and formatter (Biome)
- `npm run lint` - Run ESLint
- `npm run storybook` - Start Storybook
- `npm run service-sync` - Sync API types from backend

## Code Organization

- **Flat structure**: Components, tests, and stories live together
- **Index exports**: Each directory exports public APIs via `index.ts`
- **Domain organization**: Components organized by Prefect domain (flows, deployments, etc.)
- **Namespace awareness**: Component names consider their directory context

## Quality Standards

- **Always write tests** for new components and hooks
- **Always create Storybook stories** for new components
- **Run `npm run check`** after creating components/hooks
- **Check functionality** in browser during development
- **Mock all API calls** using MSW

## API Integration

- Use **`useSuspenseQuery`** over `useQuery` for declarative code
- **Query factories** in `/api` directories with standardized key patterns
- **Mutation hooks** in `/api` directories
- **No data transformation** in query factories - do it in components

## Forms

- **react-hook-form** for form state
- **zod** for validation
- **Form** and **FormField** components from shadcn/ui
- **Stepper** component for wizard flows

## Testing

- **Vitest** with **@testing-library/react**
- All API calls mocked with **MSW**
- Mock factories using **@ngneat/falso**
- Run single tests for performance: `npm test -- ComponentName`

## Git Workflow

- Branch naming: `ui-v2/feature-description`
- Succinct commit messages
- PR descriptions mention "Related to #15512"
- Never commit directly to `main`

## Architecture Notes

- **Suspense-first**: Use suspense queries to avoid loading states
- **Type safety**: Never use `as unknown` or disable ESLint
- **Pure functions**: Keep utilities side-effect free
- **Composition**: Prefer composition over complex inheritance