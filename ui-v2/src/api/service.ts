import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./prefect.ts";
import { uiSettings } from "./ui-settings";

const AUTH_STORAGE_KEY = "prefect-password";

const throwOnError: Middleware = {
	async onResponse({ response }) {
		if (!response.ok) {
			const body = (await response.clone().json()) as Record<string, unknown>;
			throw new Error(body.detail as string | undefined);
		}
	},
};

const authMiddleware: Middleware = {
	onRequest({ request }) {
		const password = localStorage.getItem(AUTH_STORAGE_KEY);
		if (password) {
			request.headers.set("Authorization", `Basic ${password}`);
		}
		return request;
	},
};

let client: ReturnType<typeof createClient<paths>> | null = null;
let clientBaseUrl: string | null = null;

/**
 * Get the API query service client.
 * On first call, fetches the API URL from /ui-settings endpoint.
 * Subsequent calls return the cached client.
 */
export const getQueryService = async () => {
	const apiUrl = await uiSettings.getApiUrl();

	// Create new client if URL changed or not initialized
	if (!client || clientBaseUrl !== apiUrl) {
		client = createClient<paths>({
			baseUrl: apiUrl,
		});
		client.use(authMiddleware);
		client.use(throwOnError);
		clientBaseUrl = apiUrl;
	}

	return client;
};

/**
 * Get API URL for use in raw fetch calls.
 * Prefer using getQueryService() when possible.
 */
export const getApiUrl = async (): Promise<string> => {
	return uiSettings.getApiUrl();
};
