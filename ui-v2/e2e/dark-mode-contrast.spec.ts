import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

const KEY_PAGES = [
	{ name: "Dashboard", path: "/" },
	{ name: "Flows", path: "/flows" },
	{ name: "Runs", path: "/runs" },
	{ name: "Work Pools", path: "/work-pools" },
	{ name: "Deployments", path: "/deployments" },
];

test.describe("Dark mode contrast - WCAG AA", () => {
	for (const { name, path } of KEY_PAGES) {
		test(`${name} has no contrast violations in light mode`, async ({
			page,
		}) => {
			await page.goto(path);
			await page.waitForLoadState("networkidle");
			const results = await new AxeBuilder({ page })
				.withTags(["wcag2aa"])
				.analyze();
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
			const results = await new AxeBuilder({ page })
				.withTags(["wcag2aa"])
				.analyze();
			const contrastViolations = results.violations.filter(
				(v) => v.id === "color-contrast",
			);
			expect(contrastViolations).toHaveLength(0);
		});
	}
});
