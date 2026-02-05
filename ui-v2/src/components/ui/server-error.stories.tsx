import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import type { ServerError } from "@/api/error-utils";
import { ServerErrorDisplay } from "./server-error";

const meta: Meta<typeof ServerErrorDisplay> = {
	title: "UI/ServerErrorDisplay",
	component: ServerErrorDisplay,
	parameters: {
		layout: "fullscreen",
		docs: {
			description: {
				component:
					"ServerErrorDisplay is shown when the Prefect server is unreachable or returns an error. It provides automatic retry with a countdown and manual retry option.",
			},
		},
	},
	args: {
		onRetry: fn(),
	},
};
export default meta;

type Story = StoryObj<typeof ServerErrorDisplay>;

const networkError: ServerError = {
	type: "network-error",
	message: "Unable to connect to Prefect server",
	details:
		"The server may be down, starting up, or there may be a network issue. The app will automatically retry.",
};

const serverError: ServerError = {
	type: "server-error",
	message: "Prefect server error",
	details: "The server returned an error (500). This may be a temporary issue.",
	statusCode: 500,
};

const clientError: ServerError = {
	type: "client-error",
	message: "Configuration error",
	details:
		"The server rejected the request (404). Check your Prefect configuration.",
	statusCode: 404,
};

const unknownError: ServerError = {
	type: "unknown-error",
	message: "Unexpected error",
	details: "An unexpected error occurred. Please try again.",
};

export const NetworkError: Story = {
	name: "Network Error (Server Unreachable)",
	args: {
		error: networkError,
	},
};

export const ServerError500: Story = {
	name: "Server Error (500)",
	args: {
		error: serverError,
	},
};

export const ClientError404: Story = {
	name: "Client Error (404)",
	args: {
		error: clientError,
	},
};

export const UnknownError: Story = {
	name: "Unknown Error",
	args: {
		error: unknownError,
	},
};
