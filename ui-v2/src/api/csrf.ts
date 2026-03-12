import type { Middleware } from "openapi-fetch";
import type { components } from "./prefect";
import { uiSettings } from "./ui-settings";

type CsrfTokenResponse = components["schemas"]["CsrfToken"];

const AUTH_STORAGE_KEY = "prefect-password";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Manages CSRF token lifecycle: fetching, caching, and automatic refresh.
 * Mirrors the behavior of the Vue UI's CsrfTokenApi.
 */
class CsrfTokenManager {
	private token: CsrfTokenResponse | null = null;
	private clientId: string = crypto.randomUUID();
	private ongoingFetch: Promise<CsrfTokenResponse> | null = null;
	private refreshTimer: ReturnType<typeof setTimeout> | null = null;
	private initialized = false;

	/**
	 * Initialize background token refresh if CSRF is enabled.
	 * Called lazily on first request rather than at module load time.
	 */
	private async ensureInitialized(): Promise<boolean> {
		if (this.initialized) {
			const settings = await uiSettings.load();
			return settings.csrfEnabled;
		}
		this.initialized = true;

		const settings = await uiSettings.load();
		if (!settings.csrfEnabled) {
			return false;
		}

		this.scheduleRefresh();
		return true;
	}

	/**
	 * Get a valid CSRF token, fetching a new one if needed.
	 */
	async getToken(): Promise<CsrfTokenResponse> {
		if (this.token && !this.isExpired()) {
			return this.token;
		}
		return this.fetchToken();
	}

	/**
	 * Fetch a new CSRF token from the server.
	 * Deduplicates concurrent requests.
	 */
	private async fetchToken(): Promise<CsrfTokenResponse> {
		if (this.ongoingFetch) {
			return this.ongoingFetch;
		}

		this.ongoingFetch = (async () => {
			try {
				const apiUrl = await uiSettings.getApiUrl();
				const headers: Record<string, string> = {};
				const password = localStorage.getItem(AUTH_STORAGE_KEY);
				if (password) {
					headers.Authorization = `Basic ${password}`;
				}

				const response = await fetch(
					`${apiUrl}/csrf-token?client=${this.clientId}`,
					{ headers },
				);

				if (!response.ok) {
					throw new Error(`Failed to fetch CSRF token: ${response.status}`);
				}

				const data = (await response.json()) as CsrfTokenResponse;
				this.token = data;
				this.scheduleRefresh();
				return data;
			} finally {
				this.ongoingFetch = null;
			}
		})();

		return this.ongoingFetch;
	}

	/**
	 * Force refresh the token (e.g., after an invalid token error).
	 */
	async refreshToken(): Promise<CsrfTokenResponse> {
		this.token = null;
		return this.fetchToken();
	}

	/**
	 * Check whether CSRF is enabled and attach headers if so.
	 * Returns true if headers were added.
	 */
	async addCsrfHeaders(request: Request): Promise<boolean> {
		const enabled = await this.ensureInitialized();
		if (!enabled) {
			return false;
		}

		const token = await this.getToken();
		request.headers.set("Prefect-Csrf-Token", token.token);
		request.headers.set("Prefect-Csrf-Client", this.clientId);
		return true;
	}

	private isExpired(): boolean {
		if (!this.token) return true;
		return new Date() >= new Date(this.token.expiration);
	}

	/**
	 * Schedule a background refresh at 75% of the token's remaining time
	 * until expiration, matching the Vue UI's refresh strategy.
	 *
	 * Uses Date.now() as the base rather than token.created because the
	 * server preserves the original created timestamp on upserts while
	 * only updating token and expiration.
	 */
	private scheduleRefresh(): void {
		if (this.refreshTimer) {
			clearTimeout(this.refreshTimer);
		}

		if (!this.token) {
			return;
		}

		const now = Date.now();
		const expiration = new Date(this.token.expiration).getTime();
		const timeUntilExpiry = expiration - now;
		const delay = Math.max(0, timeUntilExpiry * 0.75);

		this.refreshTimer = setTimeout(() => {
			void this.fetchToken();
		}, delay);
	}

	/**
	 * Reset state (useful for testing).
	 */
	reset(): void {
		this.token = null;
		this.ongoingFetch = null;
		this.initialized = false;
		if (this.refreshTimer) {
			clearTimeout(this.refreshTimer);
			this.refreshTimer = null;
		}
		this.clientId = crypto.randomUUID();
	}
}

export const csrfTokenManager = new CsrfTokenManager();

/**
 * openapi-fetch middleware that attaches CSRF token headers
 * to mutating requests (POST, PUT, PATCH, DELETE).
 */
export const csrfMiddleware: Middleware = {
	async onRequest({ request }) {
		if (MUTATING_METHODS.has(request.method)) {
			await csrfTokenManager.addCsrfHeaders(request);
		}
		return request;
	},
};
