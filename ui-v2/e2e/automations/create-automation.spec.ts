import { expect, test } from "../fixtures";

test.describe("Create Automation", () => {
	test("placeholder test for automation creation", async ({ page }) => {
		await page.goto("/automations");
		await expect(page).toHaveURL(/automations/);
	});
});
