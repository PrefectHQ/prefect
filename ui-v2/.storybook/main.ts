import type { StorybookConfig } from "@storybook/react-vite";

export default {
	stories: ["../src/**/*.mdx", "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"],
	addons: [
		"@storybook/addon-essentials",
		"@storybook/addon-interactions",
		"@storybook/addon-a11y",
	],
	framework: {
		name: "@storybook/react-vite",
		options: {},
	},
	/*
	 * 👇 The `config` argument contains all the other existing environment variables.
	 * Either configured in an `.env` file or configured on the command line.
	 */
	env: (config) => ({
		...config,
		VITE_API_URL: "http://localhost:6006/api",
	}),
} satisfies StorybookConfig;
