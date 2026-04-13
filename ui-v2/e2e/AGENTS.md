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

**Strict mode and confirmation dialogs**: When a confirmation dialog contains the item name (e.g., "Are you sure you want to delete `<name>`?"), asserting `getByText(name)` is gone will fail in strict mode because the name matches both the table row and the dialog description simultaneously. Always wait for the dialog to close before asserting the item's absence, and scope the final assertion to the list/table to avoid matching unrelated page elements (e.g., breadcrumbs, headers):

```typescript
// ✅ Good - wait for dialog to close, then scope assertion to the table
const deleteDialog = page.getByRole("alertdialog");
await deleteDialog.getByRole("button", { name: "Delete" }).click();
await expect(deleteDialog).not.toBeVisible();
await expect(page.getByRole("table").getByText(itemName)).not.toBeVisible();

// ❌ Bad - strict mode violation if dialog still visible
await page.getByRole("button", { name: "Delete" }).click();
await expect(page.getByText(itemName)).not.toBeVisible();
```

### Test Isolation

- Use unique test data with `TEST_PREFIX` and timestamps: `${TEST_PREFIX}item-${Date.now()}`
- Clean up in both `beforeEach` and `afterEach`
- Never depend on data from other tests

### Parallel Test Execution

Tests run with multiple workers in CI (configured in `playwright.config.ts`). This means tests can run simultaneously, which introduces potential race conditions. Follow these patterns to write resilient tests:

**Use unique identifiers for ALL test data:**

```typescript
// ✅ Good - unique per test run, won't conflict with parallel tests
const variableName = `${TEST_PREFIX}my-var-${Date.now()}`;

// ❌ Bad - fixed names can be deleted by parallel test cleanup
const variableName = `${TEST_PREFIX}my-var`;
```

**Handle eventual consistency with `expect.poll()`:**

When verifying data via API after a UI action, the API might return stale data. Use `expect.poll()` to retry until the expected data appears:

```typescript
// ✅ Good - retries until data is available
await expect
  .poll(
    async () => {
      const items = await listItems(apiClient);
      return items.find((i) => i.name === itemName)?.value;
    },
    { timeout: 5000 },
  )
  .toBe(expectedValue);

// ❌ Bad - may fail due to eventual consistency
const items = await listItems(apiClient);
expect(items.find((i) => i.name === itemName)?.value).toBe(expectedValue);
```

**Re-verify global state after navigation:**

Tests that skip based on a pre-navigation API check (e.g., "skip if no artifacts exist") must re-verify after the page loads. Another shard may have changed global state between the check and navigation, hiding a real rendering bug behind a skip:

```typescript
// ✅ Good - re-verify after page load so rendering bugs still surface
const preCheck = await listItems(apiClient);
test.skip(preCheck.length > 0, "Items exist, skipping empty-state test");

await page.goto("/items");
await waitForPageReady(page);

const recheck = await listItems(apiClient);
test.skip(recheck.length > 0, "Items appeared from another shard");

await expect(page.getByRole("heading", { name: /get started/i })).toBeVisible();
```

**Isolate test data by test file:**

Each test file should use its own `TEST_PREFIX` or unique identifiers to avoid conflicts with other test files running in parallel.

### Handling Page Loading States

When tests navigate to a page and immediately interact with it, the page might not be fully loaded, especially under parallel execution when the API server is handling multiple requests. Always wait for the page to be ready before interacting:

**Create page-ready helpers:**

```typescript
async function waitForPageReady(page: Page): Promise<void> {
  // Wait for either the empty state or the data table to be visible
  await expect(
    page
      .getByRole("heading", { name: /add an item to get started/i })
      .or(page.getByRole("table")),
  ).toBeVisible();
}
```

**Use the helper before interactions:**

```typescript
test("should create an item", async ({ page }) => {
  await page.goto("/items");
  await waitForPageReady(page); // Ensures page is loaded

  await page.getByRole("button", { name: /add item/i }).click();
  // ... rest of test
});
```

**When to use page-ready helpers:**

- Tests that click buttons immediately after navigation
- Tests that interact with elements that depend on API data loading
- Tests that run in the "Create" or "Empty State" describe blocks

**When page-ready helpers are NOT needed:**

- Tests that already wait for specific data to appear (e.g., `await expect(page.getByText(itemName)).toBeVisible()`)
- Tests that verify the empty state itself (the assertion serves as the wait)

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

### Event Timestamp Pitfall

The events page uses `roundToMinute()` to truncate the query's "until" boundary to the start of the current minute. This means **events emitted in the current minute will not appear in the UI**.

When writing tests that emit events and then assert they appear on the events page, backdate the `occurred` timestamp by at least 2 minutes:

```typescript
const occurred = new Date(Date.now() - 2 * 60_000).toISOString();
await emitEvents(apiClient, [
  buildTestEvent({ event: "...", resourceId: "...", occurred }),
]);
```

The `buildTestEvent()` helper in `e2e/fixtures/api-helpers/events.ts` accepts an optional `occurred` parameter (defaults to `new Date().toISOString()`). Tests that don't backdate will be flaky — passing when the minute boundary doesn't fall mid-test, failing when it does.

### Events Page Pagination Pitfall

The events page displays at most 50 events in descending chronological order. In busy CI environments, parallel shards generate background events (deployment runs, work-pool polls, etc.) that can push test-specific events off the first page, causing assertions to fail even though the events were emitted correctly.

Scope events-page tests to specific resources using the `resource` query parameter:

```typescript
const resourceFilter = encodeURIComponent(
  JSON.stringify([
    flowRunResourceId,
    "prefect.deployment.",
    "prefect.work-pool.",
  ]),
);
await page.goto(`/events?resource=${resourceFilter}`);
```

Pass the resource IDs (or prefixes) of the resources your test cares about. This keeps the result set small regardless of how much background activity other shards produce.

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
