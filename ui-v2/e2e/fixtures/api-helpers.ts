import type { APIRequestContext } from "@playwright/test";

export class ApiHelpers {
	constructor(private request: APIRequestContext) {}

	async getHealth(): Promise<boolean> {
		const response = await this.request.get("/api/health");
		return response.ok();
	}
}
