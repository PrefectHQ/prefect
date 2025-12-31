import path from "node:path";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vitest/config";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
	const base =
		mode === "development" ? "" : "/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER";

	return {
		base,
		plugins: [react(), TanStackRouterVite()],
		test: {
			globals: true,
			environment: "jsdom",
			setupFiles: "./tests/setup.ts",
			pool: "threads",
			exclude: ["e2e/**", "node_modules/**"],
			coverage: {
				exclude: ["**/*.stories.tsx", "**/*.test.tsx"],
			},
			env: {
				TZ: "UTC",
			},
		},
		resolve: {
			alias: {
				"@": path.resolve(__dirname, "./src"),
				"@tests": path.resolve(__dirname, "./tests"),
			},
		},
		build: {
			sourcemap: true,
		},
	};
});
