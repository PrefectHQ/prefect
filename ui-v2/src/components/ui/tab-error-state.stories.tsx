import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { TabErrorState } from "./tab-error-state";

const meta: Meta<typeof TabErrorState> = {
	title: "UI/TabErrorState",
	component: TabErrorState,
	parameters: {
		docs: {
			description: {
				component:
					"TabErrorState displays an error message within a tab content area with an optional retry button.",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		error: {
			type: "server-error",
			message: "Failed to load data",
			details: "The server returned an unexpected error. Please try again.",
		},
	},
};

export const NetworkError: Story = {
	args: {
		error: {
			type: "network-error",
			message: "Failed to load logs",
			details: "The server may be down or there may be a network issue.",
		},
		onRetry: fn(),
	},
};

export const ServerError: Story = {
	args: {
		error: {
			type: "server-error",
			message: "Failed to load task runs",
			details: "The server returned an error. This may be a temporary issue.",
		},
		onRetry: fn(),
	},
};

export const Retrying: Story = {
	args: {
		error: {
			type: "network-error",
			message: "Failed to load artifacts",
		},
		onRetry: fn(),
		isRetrying: true,
	},
};

export const NoRetry: Story = {
	args: {
		error: {
			type: "unknown-error",
			message: "Something went wrong",
			details: "Please refresh the page.",
		},
	},
};

export const NoDetails: Story = {
	args: {
		error: {
			type: "unknown-error",
			message: "Something went wrong",
		},
	},
};
