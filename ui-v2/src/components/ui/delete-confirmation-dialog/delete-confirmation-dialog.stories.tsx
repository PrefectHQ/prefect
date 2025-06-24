import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";

import { DeleteConfirmationDialog } from "./index";

const meta = {
	title: "UI/DeleteConfirmationDialog",
	component: DeleteConfirmationDialog,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof DeleteConfirmationDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		isOpen: true,
		title: "Delete Item",
		description:
			"Are you sure you want to delete this item? This action cannot be undone.",
		onConfirm: fn(),
		onClose: fn(),
	},
};

export const WithCustomText: Story = {
	args: {
		isOpen: true,
		title: "Delete User Account",
		description:
			"This will permanently delete the user account and all associated data. This action is irreversible.",
		onConfirm: fn(),
		onClose: fn(),
	},
};
