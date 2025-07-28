import type { Meta, StoryObj } from "@storybook/react";

import { Badge } from "@/components/ui/badge";

import { KeyValueDisplay } from "./key-value-display";

const meta = {
	title: "UI/KeyValueDisplay",
	component: KeyValueDisplay,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
} satisfies Meta<typeof KeyValueDisplay>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		items: [
			{ key: "Name", value: "My Work Pool" },
			{ key: "Type", value: "docker" },
			{ key: "Status", value: "active" },
			{ key: "Created", value: "2024-01-15" },
			{ key: "Concurrency Limit", value: "10" },
			{
				key: "Description",
				value: "A work pool for running Docker containers",
			},
		],
	},
};

export const WithReactNodes: Story = {
	args: {
		items: [
			{ key: "Name", value: "My Work Pool" },
			{
				key: "Status",
				value: <Badge variant="default">Active</Badge>,
			},
			{ key: "Type", value: "docker" },
			{
				key: "Actions",
				value: (
					<div className="flex gap-2">
						<button
							type="button"
							className="px-2 py-1 text-xs bg-blue-500 text-white rounded"
						>
							Edit
						</button>
						<button
							type="button"
							className="px-2 py-1 text-xs bg-red-500 text-white rounded"
						>
							Delete
						</button>
					</div>
				),
			},
		],
	},
};

export const Compact: Story = {
	args: {
		variant: "compact",
		items: [
			{ key: "Name", value: "My Work Pool" },
			{ key: "Type", value: "docker" },
			{ key: "Status", value: "active" },
			{ key: "Created", value: "2024-01-15" },
		],
	},
};

export const WithHiddenItems: Story = {
	args: {
		items: [
			{ key: "Name", value: "My Work Pool" },
			{ key: "Type", value: "docker" },
			{ key: "Hidden Field", value: "This won't show", hidden: true },
			{ key: "Status", value: "active" },
		],
	},
};

export const SingleColumn: Story = {
	args: {
		items: [
			{
				key: "Long Description",
				value:
					"This is a very long description that should span the full width and not be constrained to a grid column",
			},
		],
	},
};

export const Empty: Story = {
	args: {
		items: [],
	},
};
