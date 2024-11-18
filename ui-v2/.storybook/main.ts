import type { StorybookConfig } from "@storybook/react-vite";

export default {
	stories: ["../src/**/*.mdx", "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"],
	addons: ["@storybook/addon-essentials", "@storybook/addon-interactions"],
	framework: {
		name: "@storybook/react-vite",
		options: {},
	},
} satisfies StorybookConfig;
