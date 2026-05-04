import path from "node:path";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
	const base =
		mode === "development" ? "" : "/PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER";

	return {
		base,
		plugins: [
			TanStackRouterVite({
				autoCodeSplitting: !process.env.VITEST,
			}),
			react(),
		],
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
			rollupOptions: {
				output: {
					manualChunks(id) {
						// React core - loaded on every page
						if (
							id.includes("node_modules/react-dom/") ||
							id.includes("node_modules/react/")
						) {
							return "vendor-react";
						}
						// TanStack ecosystem - loaded on every page
						if (id.includes("node_modules/@tanstack/")) {
							return "vendor-tanstack";
						}
						// Charts - only needed on dashboard and detail pages
						if (id.includes("node_modules/recharts/")) {
							return "vendor-recharts";
						}
						// Code editor - only needed on blocks/automations edit pages
						if (
							id.includes("node_modules/@codemirror/") ||
							id.includes("node_modules/@uiw/react-codemirror/")
						) {
							return "vendor-codemirror";
						}
						// Radix UI primitives - used throughout
						if (id.includes("node_modules/@radix-ui/")) {
							return "vendor-radix";
						}
						// Date utilities - used on dashboard and scheduling pages
						if (
							id.includes("node_modules/date-fns/") ||
							id.includes("node_modules/date-fns-tz/") ||
							id.includes("node_modules/cron-parser/") ||
							id.includes("node_modules/cronstrue/") ||
							id.includes("node_modules/rrule/")
						) {
							return "vendor-date";
						}
						// Graph visualization - only needed on flow run detail pages
						if (
							id.includes("node_modules/pixi.js/") ||
							id.includes("node_modules/pixi-viewport/") ||
							id.includes("node_modules/@pixi/")
						) {
							return "vendor-pixi";
						}
						// Form handling - used in create/edit pages
						if (
							id.includes("node_modules/react-hook-form/") ||
							id.includes("node_modules/@hookform/") ||
							id.includes("node_modules/zod/")
						) {
							return "vendor-forms";
						}
						// Markdown rendering - used in artifact display
						if (
							id.includes("node_modules/react-markdown/") ||
							id.includes("node_modules/remark-gfm/")
						) {
							return "vendor-markdown";
						}
						// Mermaid diagram rendering - lazily loaded by markdown blocks
						if (
							id.includes("node_modules/mermaid/") ||
							id.includes("node_modules/dagre-d3-es/") ||
							id.includes("node_modules/cytoscape") ||
							id.includes("node_modules/khroma/") ||
							id.includes("node_modules/elkjs/")
						) {
							return "vendor-mermaid";
						}
					},
				},
			},
		},
	};
});
