import type { Meta, StoryObj } from "@storybook/react";

import { DocsLink } from "./docs-link";

const meta: Meta<typeof DocsLink> = {
	title: "UI/DocsLink",
	component: DocsLink,
	parameters: {
		docs: {
			description: {
				component:
					"DocsLink is used to open the docs page for a specific feature",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof DocsLink>;
export const Usage: Story = {
	args: {
		id: "global-concurrency-guide",
	},
};
