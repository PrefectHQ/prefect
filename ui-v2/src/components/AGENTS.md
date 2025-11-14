# Components Directory

This directory contains React components for the Prefect UI migration from Vue to React.

## Tech Stack
- React with TypeScript
- Tailwind CSS for styling
- shadcn/ui component library

## Organization

- Code, test, and storybook files should be contained in the same directory
- Include an `index.ts` file that exports components that are part of the "public API" of the directory

## Component Guidelines

- ALWAYS check @prefect/ui-v2/src/components/ui before creating a new component
- ALWAYS create a Storybook story when creating a new component
- ALWAYS write tests when creating a new component
- Consider the current directory namespace when naming components to avoid duplication
- Prefer flat component structures over nested ones
- If creating nested components for readability, keep them in the same file as the parent component

  ## Using Existing Components

  Before creating any UI element:
  1. Check `@/components/ui` for atomic components (buttons, cards, icons)
  2. Check sibling directories for domain-specific components (e.g., `work-pools/work-pool-status-icon`)
  3. Import and reuse rather than recreate

## Forms

- Use `react-hook-form` for forms
- Use `zod` for form validation
- Use `zod-form-adapter` to convert `zod` schemas to `react-hook-form` form schemas
- Use `Form` component from `@/components/ui/form` to wrap forms
- Use `FormField` component from `@/components/ui/form` to wrap form fields
- Use `Stepper` component for wizard-like flows

## Icon Usage

  - Import icons from `lucide-react`
  - Check existing icon components in domain directories first
  - Common pattern: icon components should accept `status` or similar prop, not full entity objects
  - Use wrapper components to transform entity data into icon props

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

## Storybook Best Practices

  - **Decorators**: Include `reactQueryDecorator` and `routerDecorator` for components using queries/routing
  - **Mock Data**: Use MSW handlers, NOT `prefetchedQueries` parameter
  - **Testing Stories**: Always test stories in browser before considering complete
  - Import `buildApiUrl` from `@tests/utils/handlers` for MSW handlers
  - Import `HttpResponse, http` from `msw`

  Example:
  ```tsx
  import { buildApiUrl } from "@tests/utils/handlers";
  import { HttpResponse, http } from "msw";

  const meta = {
    decorators: [reactQueryDecorator, routerDecorator],
    // ...
  } satisfies Meta<typeof MyComponent>;

  export const Default: Story = {
    parameters: {
      msw: {
        handlers: [
          http.post(buildApiUrl("/endpoint"), () => {
            return HttpResponse.json(mockData);
          }),
        ],
      },
    },
  };
  ```

### Verification Checklist

Before committing stories:
- Decorators included (reactQueryDecorator, routerDecorator)
- MSW handlers (not prefetchedQueries)
- Stories render in Storybook UI without errors
- Mock data uses factory functions from @/mocks
- All component states have corresponding stories

  ## For `/Users/alexander/dev/PrefectHQ/oss-ui-replatform/prefect/ui-v2/src/storybook/CLAUDE.md`

  Replace the existing content with more specific guidance:

  # Storybook Directory

  This directory contains Storybook utilities and decorators.

  ## Required Imports for Stories

  ```tsx
  import type { Meta, StoryObj } from "@storybook/react";
  import { buildApiUrl } from "@tests/utils/handlers";
  import { HttpResponse, http } from "msw";
  import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
  ```

  Decorator Usage

  - reactQueryDecorator: Required for components using useQuery, useSuspenseQuery, or useMutation
  - routerDecorator: Required for components using Link, useNavigate, or other Tanstack Router hooks
  - toastDecorator: Required for components using toasts

  Most components need both reactQueryDecorator and routerDecorator:

  ```tsx
  const meta = {
    title: "Components/MyComponent",
    component: MyComponent,
    decorators: [reactQueryDecorator, routerDecorator],
  } satisfies Meta<typeof MyComponent>;

  ```

  Mocking API Calls with MSW

  NEVER use prefetchedQueries parameter - it doesn't work with Storybook's setup.

  ALWAYS use MSW handlers:

  ```tsx
  export const MyStory: Story = {
    parameters: {
      msw: {
        handlers: [
          http.post(buildApiUrl("/api/endpoint"), () => {
            return HttpResponse.json(mockData);
          }),
        ],
      },
    },
  };
  ```
  Common Patterns

  Multiple API Endpoints


  ```tsx
  parameters: {
    msw: {
      handlers: [
        http.post(buildApiUrl("/work_pools/filter"), () => {
          return HttpResponse.json(workPoolsData);
        }),
        http.get(buildApiUrl("/flows/:id"), () => {
          return HttpResponse.json(flowData);
        }),
      ],
    },
  }
  ```

  Different Stories, Different Data

  ```tsx
  export const WithData: Story = {
    parameters: {
      msw: {
        handlers: [
          http.post(buildApiUrl("/endpoint"), () => {
            return HttpResponse.json([item1, item2]);
          }),
        ],
      },
    },
  };

  export const EmptyState: Story = {
    parameters: {
      msw: {
        handlers: [
          http.post(buildApiUrl("/endpoint"), () => {
            return HttpResponse.json([]);
          }),
        ],
      },
    },
  };
  ```
