import path from "node:path";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [react(), TanStackRouterVite()],
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: "./tests/setup.ts",
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
});
