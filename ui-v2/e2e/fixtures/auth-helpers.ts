import type { Page } from "@playwright/test";
import type { PrefectApiClient } from "./api-client";

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

/**
 * Check if the server requires authentication by querying the /ui-settings endpoint.
 * Returns true if auth is set to "BASIC", false otherwise.
 */
export async function isAuthRequired(
	client: PrefectApiClient,
): Promise<boolean> {
	const { data, error } = await client.GET("/ui-settings");
	if (error) {
		throw new Error(`Failed to fetch UI settings: ${JSON.stringify(error)}`);
	}
	return data.auth === "BASIC";
}
