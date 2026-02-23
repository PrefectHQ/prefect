import AxeBuilder from "@axe-core/playwright";
import {
	cleanupDeployments,
	cleanupFlowRuns,
	cleanupFlows,
	cleanupWorkPools,
	createDeployment,
	createFlow,
	createFlowRun,
	createWorkPool,
	expect,
	test,
	waitForServerHealth,
} from "./fixtures";

const KEY_PAGES = [
	{ name: "Dashboard", path: "/" },
	{ name: "Flows", path: "/flows" },
	{ name: "Runs", path: "/runs" },
	{ name: "Work Pools", path: "/work-pools" },
	{ name: "Deployments", path: "/deployments" },
];

// CSS selectors for elements with known pre-existing contrast issues
// that are outside the scope of the state-color consistency work.
// Breadcrumb page titles use a foreground/background combination that
// does not meet WCAG AA 4.5:1 for normal text. These should be
// addressed in a dedicated breadcrumb-styling follow-up.
const EXCLUDED_SELECTORS = [
	'[data-slot="breadcrumb-item"]',
	'nav[aria-label="breadcrumb"] li',
];

const STATE_TYPES = [
	"COMPLETED",
	"FAILED",
	"RUNNING",
	"CANCELLED",
	"CRASHED",
	"PAUSED",
	"PENDING",
	"SCHEDULED",
] as const;

const PREFIX = "e2e-contrast-";

test.describe("Dark mode contrast - WCAG AA", () => {
	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ apiClient }) => {
		await waitForServerHealth(apiClient);

		const flow = await createFlow(apiClient, `${PREFIX}flow-${Date.now()}`);
		const workPool = await createWorkPool(apiClient, {
			name: `${PREFIX}pool-${Date.now()}`,
		});
		await createDeployment(apiClient, {
			name: `${PREFIX}deploy-${Date.now()}`,
			flowId: flow.id,
			workPoolName: workPool.name,
		});

		for (const stateType of STATE_TYPES) {
			await createFlowRun(apiClient, {
				flowId: flow.id,
				name: `${PREFIX}${stateType.toLowerCase()}-${Date.now()}`,
				state: { type: stateType },
			});
		}
	});

	test.afterAll(async ({ apiClient }) => {
		try {
			await cleanupFlowRuns(apiClient, PREFIX);
			await cleanupDeployments(apiClient, PREFIX);
			await cleanupFlows(apiClient, PREFIX);
			await cleanupWorkPools(apiClient, PREFIX);
		} catch {
			// Ignore cleanup errors
		}
	});

	for (const { name, path } of KEY_PAGES) {
		test(`${name} has no contrast violations in light mode`, async ({
			page,
		}) => {
			await page.goto(path);
			await page.waitForLoadState("networkidle");
			let builder = new AxeBuilder({ page });
			for (const sel of EXCLUDED_SELECTORS) {
				builder = builder.exclude(sel);
			}
			const results = await builder.withTags(["wcag2aa"]).analyze();
			const contrastViolations = results.violations.filter(
				(v) => v.id === "color-contrast",
			);
			expect(contrastViolations).toHaveLength(0);
		});

		test(`${name} has no contrast violations in dark mode`, async ({
			page,
		}) => {
			await page.addInitScript(() => {
				localStorage.setItem("vite-ui-theme", "dark");
			});
			await page.goto(path);
			await page.waitForLoadState("networkidle");
			let builder = new AxeBuilder({ page });
			for (const sel of EXCLUDED_SELECTORS) {
				builder = builder.exclude(sel);
			}
			const results = await builder.withTags(["wcag2aa"]).analyze();
			const contrastViolations = results.violations.filter(
				(v) => v.id === "color-contrast",
			);
			expect(contrastViolations).toHaveLength(0);
		});
	}
});
