/// <reference types="vite/client" />

interface ImportMetaEnv {
	/**
	 * Development-only API URL override.
	 * In production, the API URL is discovered from /ui-settings endpoint.
	 * Only used when running `npm run dev`.
	 */
	readonly VITE_API_URL?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
