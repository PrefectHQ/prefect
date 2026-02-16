# Storybook Directory

This directory contains Storybook utilities and decorators.

## Storybook Guidelines

- ALWAYS create a Storybook story when creating a new component
- Structure stories to showcase different component states
- Use mock data from `@prefect/ui-v2/src/mocks` for realistic examples
- Use `fn` from `storybook/test` for callback functions
- When mocking with `msw`, use `buildApiUrl` from `@tests/utils/handlers` to build URLs
- Decorators for stories are available in `@prefect/ui-v2/src/storybook/utils`
- Use decorators for components that rely on `queryClient` and `router` objects

## Required Decorators

- reactQueryDecorator: Required for components using useQuery, useSuspenseQuery, or useMutation
- routerDecorator: Required for components using Link, useNavigate, or other Tanstack Router hooks
- toastDecorator: Required for components using toasts

Most components need both `reactQueryDecorator` and `routerDecorator`:

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";

const meta = {
title: "Components/MyComponent",
component: MyComponent,
decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof MyComponent>;

```

## Mocking API Calls with MSW

- ALWAYS use MSW handlers when mocking API calls:

```tsx
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";

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

### Common Patterns

#### Multiple API Endpoints

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

#### Different Stories, Different Data

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