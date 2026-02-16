import type { Page } from "@playwright/test";
import {
	cleanupDeployments,
	cleanupFlows,
	createDeployment,
	createFlow,
	expect,
	test,
	waitForServerHealth,
} from "../fixtures";

const TEST_PREFIX = "e2e-dep-list-";

async function waitForDeploymentsPageReady(page: Page): Promise<void> {
	await expect(
		page
			.getByRole("heading", { name: /create a deployment to get started/i })
			.or(page.getByText(/\d+ Deployments?/)),
	).toBeVisible({ timeout: 10000 });
}

test.describe("Deployments List Page", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);
	});

	test.beforeEach(async ({ apiClient }) => {
		try {
			await cleanupDeployments(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test.afterEach(async ({ apiClient }) => {
		try {
			await cleanupDeployments(apiClient, TEST_PREFIX);
			await cleanupFlows(apiClient, TEST_PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	test("Empty state when no deployments exist", async ({ page }) => {
		await page.goto("/deployments");

		const emptyStateHeading = page.getByRole("heading", {
			name: /create a deployment to get started/i,
		});
		const deploymentsCount = page.getByText(/\d+ Deployments?/);

		await expect(emptyStateHeading.or(deploymentsCount)).toBeVisible({
			timeout: 10000,
		});

		if (await emptyStateHeading.isVisible()) {
			await expect(
				page.getByText(/deployments elevate workflows/i),
			).toBeVisible();
			await expect(
				page.getByRole("link", { name: /view docs/i }),
			).toBeVisible();
		} else {
			test.skip(true, "Deployments already exist from other tests");
		}
	});

	test("Deployments list with name search", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}search-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}search-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		await createDeployment(apiClient, { name: depName, flowId: flow.id });

		await expect(async () => {
			await page.goto("/deployments");
			await expect(page.getByText(/\d+ Deployments?/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByPlaceholder("Search deployments").fill(depName);

		await expect(page).toHaveURL(/flowOrDeploymentName=/);
		await expect(page.getByText(depName)).toBeVisible({ timeout: 10000 });
	});

	test("Tag filter", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}tag-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}tag-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		await createDeployment(apiClient, {
			name: depName,
			flowId: flow.id,
			tags: ["e2e-dep-tag"],
		});

		await expect(async () => {
			await page.goto("/deployments");
			await expect(page.getByText(/\d+ Deployments?/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		const tagsInput = page.getByPlaceholder("Filter by tags");
		await tagsInput.pressSequentially("e2e-dep-tag");
		await page.keyboard.press("Enter");

		await expect(page).toHaveURL(/tags=/);
		await expect(page.getByText(depName)).toBeVisible({
			timeout: 10000,
		});
	});

	test("Sort deployments with URL persistence", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}sort-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}sort-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		await createDeployment(apiClient, { name: depName, flowId: flow.id });

		await page.goto("/deployments");
		await waitForDeploymentsPageReady(page);

		await page.getByLabel("Deployment sort order").click();
		await page.getByRole("option", { name: "Z to A" }).click();

		await expect(page).toHaveURL(/sort=NAME_DESC/);
	});

	test("Pagination", async ({ page, apiClient }) => {
		const timestamp = Date.now();
		for (let i = 0; i < 6; i++) {
			const flowName = `${TEST_PREFIX}page-flow-${timestamp}-${String(i).padStart(2, "0")}`;
			const depName = `${TEST_PREFIX}page-${timestamp}-${String(i).padStart(2, "0")}`;
			const flow = await createFlow(apiClient, flowName);
			await createDeployment(apiClient, { name: depName, flowId: flow.id });
		}

		await expect(async () => {
			await page.goto(
				`/deployments?limit=5&flowOrDeploymentName=${encodeURIComponent(`${TEST_PREFIX}page-${timestamp}`)}`,
			);
			await expect(page.getByText(/Page 1 of 2/)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("button", { name: /go to next page/i }).click();

		await expect(page).toHaveURL(/page=2/);
		await expect(page.getByText(/Page 2 of/)).toBeVisible();
	});

	test("Navigate from list to deployment detail", async ({
		page,
		apiClient,
	}) => {
		const timestamp = Date.now();
		const flowName = `${TEST_PREFIX}detail-flow-${timestamp}`;
		const depName = `${TEST_PREFIX}detail-dep-${timestamp}`;
		const flow = await createFlow(apiClient, flowName);
		await createDeployment(apiClient, { name: depName, flowId: flow.id });

		await expect(async () => {
			await page.goto(
				`/deployments?flowOrDeploymentName=${encodeURIComponent(depName)}`,
			);
			await expect(page.getByText(depName)).toBeVisible({
				timeout: 2000,
			});
		}).toPass({ timeout: 15000 });

		await page.getByRole("link", { name: depName }).click();

		await expect(page).toHaveURL(/\/deployments\/deployment\//);
		await expect(page.getByText(depName)).toBeVisible();
	});
});
