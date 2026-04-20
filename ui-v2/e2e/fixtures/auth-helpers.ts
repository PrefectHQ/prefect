import type { Page } from "@playwright/test";

const AUTH_STORAGE_KEY = "prefect-password";

/**
 * Set authentication credentials in localStorage.
 * Credentials are base64 encoded before storage.
 */
export async function setAuthCredentials(
	page: Page,
	credentials: string,
): Promise<void> {
	const encodedCredentials = Buffer.from(credentials).toString("base64");
	await page.evaluate(
		({ key, value }) => {
			localStorage.setItem(key, value);
		},
		{ key: AUTH_STORAGE_KEY, value: encodedCredentials },
	);
}

/**
 * Clear authentication credentials from localStorage.
 */
export async function clearAuthCredentials(page: Page): Promise<void> {
	await page.evaluate((key) => {
		localStorage.removeItem(key);
	}, AUTH_STORAGE_KEY);
}

/**
 * Get stored authentication credentials from localStorage.
 * Returns the base64 encoded credentials or null if not set.
 */
export async function getAuthCredentials(page: Page): Promise<string | null> {
	return page.evaluate((key) => {
		return localStorage.getItem(key);
	}, AUTH_STORAGE_KEY);
}

interface UiSettingsResponse {
	api_url: string;
	csrf_enabled: boolean;
	auth: string | null;
	flags: string[];
}

/**
 * Check if the server requires authentication by querying the /ui-settings endpoint.
 * The /ui-settings endpoint is at the root level (not under /api) and doesn't require auth.
 * Returns true if auth is set to "BASIC", false otherwise.
 */
export async function isAuthRequired(): Promise<boolean> {
	const apiUrl = process.env.PREFECT_API_URL ?? "http://localhost:4200/api";
	const baseUrl = apiUrl.replace(/\/api\/?$/, "");

	const response = await fetch(`${baseUrl}/ui-settings`);
	if (!response.ok) {
		throw new Error(`Failed to fetch UI settings: status ${response.status}`);
	}

	const data = (await response.json()) as UiSettingsResponse;
	return data.auth === "BASIC";
}
