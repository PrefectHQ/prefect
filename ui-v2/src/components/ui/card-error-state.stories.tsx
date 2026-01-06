import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { CardErrorState } from "./card-error-state";

const meta: Meta<typeof CardErrorState> = {
	title: "UI/CardErrorState",
	component: CardErrorState,
	parameters: {
		docs: {
			description: {
				component:
					"CardErrorState displays an error message within a card with an optional retry button.",
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
			message: "Unable to connect",
			details: "Check your internet connection and try again.",
		},
	},
};

export const WithRetryButton: Story = {
	args: {
		error: {
			type: "server-error",
			message: "Failed to load flow runs",
			details: "The API request timed out.",
		},
		onRetry: fn(),
	},
};

export const Retrying: Story = {
	args: {
		error: {
			type: "server-error",
			message: "Failed to load flow runs",
			details: "The API request timed out.",
		},
		onRetry: fn(),
		isRetrying: true,
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

export const NoRetryButton: Story = {
	args: {
		error: {
			type: "client-error",
			message: "Invalid request",
			details: "The request parameters were invalid.",
		},
	},
};
