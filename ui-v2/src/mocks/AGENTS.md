# Mocks Directory

This directory contains mock data factories for testing and development.

## Mock Guidelines

- Use utilities from `@ngneat/falso` to generate random data
- Create factory functions that return realistic test data
- Organize mocks by domain/resource type
- Make mocks configurable with optional parameters

## Mock Factory Pattern

```ts
import { randText, randNumber } from '@ngneat/falso';

export function createMockItem(overrides?: Partial<Item>): Item {
  return {
    id: randText(),
    name: randText(),
    count: randNumber({ min: 1, max: 100 }),
    ...overrides,
  };
}
```

## Usage

- API mocks are also in @prefect/ui-v2/src/api/mocks
- All API calls should be mocked using `msw`
- Use these factories in tests and Storybook stories