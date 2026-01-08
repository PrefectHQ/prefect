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
		plugins: [
			TanStackRouterVite({
				autoCodeSplitting: true,
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
					manualChunks: {
						// React core - loaded on every page
						"vendor-react": ["react", "react-dom"],
						// TanStack ecosystem - loaded on every page
						"vendor-tanstack": [
							"@tanstack/react-query",
							"@tanstack/react-router",
							"@tanstack/react-table",
							"@tanstack/react-virtual",
						],
						// Charts - only needed on dashboard and detail pages
						"vendor-recharts": ["recharts"],
						// Code editor - only needed on blocks/automations edit pages
						"vendor-codemirror": [
							"@codemirror/lang-json",
							"@codemirror/lang-markdown",
							"@codemirror/lang-python",
							"@uiw/react-codemirror",
						],
						// Radix UI primitives - used throughout
						"vendor-radix": [
							"@radix-ui/react-accordion",
							"@radix-ui/react-alert-dialog",
							"@radix-ui/react-avatar",
							"@radix-ui/react-checkbox",
							"@radix-ui/react-collapsible",
							"@radix-ui/react-dialog",
							"@radix-ui/react-dropdown-menu",
							"@radix-ui/react-hover-card",
							"@radix-ui/react-icons",
							"@radix-ui/react-label",
							"@radix-ui/react-menubar",
							"@radix-ui/react-popover",
							"@radix-ui/react-radio-group",
							"@radix-ui/react-scroll-area",
							"@radix-ui/react-select",
							"@radix-ui/react-separator",
							"@radix-ui/react-slot",
							"@radix-ui/react-switch",
							"@radix-ui/react-tabs",
							"@radix-ui/react-toast",
							"@radix-ui/react-toggle",
							"@radix-ui/react-toggle-group",
							"@radix-ui/react-tooltip",
						],
						// Date utilities - used on dashboard and scheduling pages
						"vendor-date": [
							"date-fns",
							"date-fns-tz",
							"cron-parser",
							"cronstrue",
							"rrule",
						],
						// Graph visualization - only needed on flow run detail pages
						"vendor-graphs": ["@prefecthq/graphs"],
						// Form handling - used in create/edit pages
						"vendor-forms": ["react-hook-form", "@hookform/resolvers", "zod"],
						// Markdown rendering - used in artifact display
						"vendor-markdown": ["react-markdown", "remark-gfm"],
					},
				},
			},
		},
	};
});
