import { test as base } from "@playwright/test";
import { ApiHelpers } from "./api-helpers";

type Fixtures = {
	api: ApiHelpers;
};

export const test = base.extend<Fixtures>({
	api: async ({ request }, use) => {
		const api = new ApiHelpers(request);
		await use(api);
	},
});

export { expect } from "@playwright/test";
