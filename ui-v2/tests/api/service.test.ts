import { describe, it, expect } from "vitest";

import type { paths } from "../../src/api/prefect";
import createClient from "openapi-fetch";

describe("API Service", () => {
	it("can paginate flows", async () => {
		const QueryService = createClient<paths>({
			baseUrl: "http://localhost:4200/api",
		});
		const flows = await QueryService.POST("/flows/paginate", {
			page: 1,
			page_size: 10,
		});
		expect(flows.data).toEqual({
			results: [
				{ id: "1", name: "Flow 1", tags: [] },
				{ id: "2", name: "Flow 2", tags: [] },
			],
		});
	});
});
