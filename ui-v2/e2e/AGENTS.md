# E2E Testing (Playwright)

This directory contains end-to-end tests using Playwright to test complete user workflows.

### Commands

```bash
npm run test:e2e        # Run all E2E tests
npm run test:e2e:ui     # Run with Playwright UI (interactive)
npm run test:e2e:debug  # Run in debug mode
```

### Test Structure

All E2E tests follow this structure:

```typescript
import { test, expect, waitForServerHealth, cleanupResources } from "../fixtures";

const TEST_PREFIX = "e2e-test-";

test.describe("Feature Name", () => {
  // Wait for server before all tests
  test.beforeAll(async ({ apiClient }) => {
    await waitForServerHealth(apiClient);
  });

  // Clean up test data before and after each test
  test.beforeEach(async ({ apiClient }) => {
    await cleanupResources(apiClient, TEST_PREFIX);
  });

  test.afterEach(async ({ apiClient }) => {
    await cleanupResources(apiClient, TEST_PREFIX);
  });

  test("should do something", async ({ page, apiClient }) => {
    // Test implementation
  });
});
```

### Selector Best Practices

Use selectors in this priority order:

1. **Role-based** (preferred): `page.getByRole("button", { name: /submit/i })`
2. **Text**: `page.getByText("Welcome")`
3. **Label**: `page.getByLabel("Email")`
4. **Placeholder**: `page.getByPlaceholder("Search...")`
5. **Test ID** (fallback): `page.getByTestId("submit-btn")`
6. **CSS selectors** (avoid): Only for third-party components without accessible roles

```typescript
// ✅ Good - role-based
await page.getByRole("button", { name: /add variable/i }).click();
await page.getByRole("textbox", { name: /name/i }).fill(value);
await page.getByRole("dialog", { name: /new variable/i });

// ✅ Good - scoped selectors for disambiguation
const dialog = page.getByRole("dialog");
const nameInput = dialog.getByRole("textbox", { name: /name/i });

// ❌ Avoid - CSS selectors (unless third-party component)
page.locator(".my-class")
page.locator("table tbody tr")
```

### Assertions

Always use auto-waiting assertions:

```typescript
// ✅ Good - auto-waiting assertions
await expect(page.getByText("Success")).toBeVisible();
await expect(page.getByRole("dialog")).not.toBeVisible();
await expect(page).toHaveURL(/\/dashboard/);

// ❌ Bad - manual assertions (don't auto-retry)
expect(await page.getByText("Success").isVisible()).toBe(true);
```

### Test Isolation

- Use unique test data with `TEST_PREFIX` and timestamps: `${TEST_PREFIX}item-${Date.now()}`
- Clean up in both `beforeEach` and `afterEach`
- Never depend on data from other tests

### Dual Verification Pattern

Verify actions through both UI and API:

```typescript
// UI verification
await expect(page.getByText(itemName)).toBeVisible();

// API verification
const items = await listItems(apiClient);
const created = items.find((i) => i.name === itemName);
expect(created).toBeDefined();
expect(created?.value).toBe(expectedValue);
```

### Explicit Waits

Avoid `waitForTimeout()` unless absolutely necessary. When required, always add a comment explaining why:

```typescript
// ✅ Acceptable - documented reason
// Wait for dialog animation to complete (200ms duration)
await page.waitForTimeout(250);

// ❌ Bad - no explanation
await page.waitForTimeout(1000);
```

### Custom Fixtures

Tests extend custom fixtures from `e2e/fixtures/`:

- `apiClient` - Type-safe Prefect API client for test setup/verification
- API helpers in `e2e/fixtures/api-helpers/` - CRUD operations for test data

### Adding New E2E Tests

1. Create test file in appropriate `e2e/` subdirectory
2. Import from `../fixtures` (includes `test`, `expect`, and all helpers)
3. Follow the test structure pattern above
4. Use role-based selectors
5. Implement dual verification (UI + API)
6. Run `npm run test:e2e:ui` to verify interactively
