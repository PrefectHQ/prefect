/// <reference types="vite/client" />

interface ImportMetaEnv {
	/**
	 * Development-only API URL override.
	 * In production, the API URL is discovered from /ui-settings endpoint.
	 * Only used when running `npm run dev`.
	 */
	readonly VITE_API_URL?: string;
	/**
	 * When set to "true", disables TanStack Router and Query devtools.
	 * Used during Playwright E2E tests to prevent devtools from interfering with tests.
	 */
	readonly VITE_DISABLE_DEVTOOLS?: string;
	/**
	 * Amplitude API key for analytics.
	 * Set at build time via environment variable.
	 */
	readonly VITE_AMPLITUDE_API_KEY?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
