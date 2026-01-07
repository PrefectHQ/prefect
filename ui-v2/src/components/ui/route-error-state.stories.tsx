import type { Meta, StoryObj } from "@storybook/react";
import { RouteErrorState } from "./route-error-state";

const meta: Meta<typeof RouteErrorState> = {
	title: "UI/RouteErrorState",
	component: RouteErrorState,
	parameters: {
		layout: "centered",
	},
};

export default meta;
type Story = StoryObj<typeof RouteErrorState>;

export const NetworkError: Story = {
	args: {
		error: {
			type: "network-error",
			message: "Unable to connect to Prefect server",
			details:
				"The server may be down, starting up, or there may be a network issue.",
		},
		onRetry: () => console.log("Retry clicked"),
	},
};

export const ServerError: Story = {
	args: {
		error: {
			type: "server-error",
			message: "Prefect server error",
			details:
				"The server returned an error (500). This may be a temporary issue.",
			statusCode: 500,
		},
		onRetry: () => console.log("Retry clicked"),
	},
};

export const ClientError: Story = {
	args: {
		error: {
			type: "client-error",
			message: "Configuration error",
			details:
				"The server rejected the request (400). Check your Prefect configuration.",
			statusCode: 400,
		},
		onRetry: () => console.log("Retry clicked"),
	},
};

export const UnknownError: Story = {
	args: {
		error: {
			type: "unknown-error",
			message: "Unexpected error",
			details: "An unexpected error occurred. Please try again.",
		},
		onRetry: () => console.log("Retry clicked"),
	},
};

export const MinimalError: Story = {
	args: {
		error: {
			type: "unknown-error",
			message: "Something went wrong",
		},
		onRetry: () => console.log("Retry clicked"),
	},
};
