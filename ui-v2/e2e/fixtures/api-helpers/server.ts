import type { PrefectApiClient } from "../api-client";

export async function waitForServerHealth(
	client: PrefectApiClient,
	timeoutMs = 30000,
): Promise<void> {
	const startTime = Date.now();
	while (Date.now() - startTime < timeoutMs) {
		const { response } = await client.GET("/health");
		if (response.ok) {
			return;
		}
		await new Promise((resolve) => setTimeout(resolve, 500));
	}
	throw new Error(`Server did not become healthy within ${timeoutMs}ms`);
}
