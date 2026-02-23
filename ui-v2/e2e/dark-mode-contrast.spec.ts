import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

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

test.describe("Dark mode contrast - WCAG AA", () => {
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
