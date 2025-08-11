import type { Meta, StoryObj } from "@storybook/react";

import { SchemaDisplay } from "./schema-display";

const meta = {
	title: "Components/Schemas/SchemaDisplay",
	component: SchemaDisplay,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
} satisfies Meta<typeof SchemaDisplay>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BasicTypes: Story = {
	args: {
		schema: {
			properties: {
				name: {
					type: "string",
					title: "Name",
					description: "The name of the item",
				},
				count: {
					type: "number",
					title: "Count",
					description: "Number of items",
				},
				enabled: {
					type: "boolean",
					title: "Enabled",
					description: "Whether the item is enabled",
				},
				tags: {
					type: "array",
					title: "Tags",
					description: "List of tags",
					items: { type: "string" },
				},
			},
		},
		data: {
			name: "My Work Pool",
			count: 42,
			enabled: true,
			tags: ["production", "docker", "important"],
		},
	},
};

export const WithDefaults: Story = {
	args: {
		schema: {
			properties: {
				image: {
					type: "string",
					title: "Docker Image",
					description: "The Docker image to use",
					default: "python:3.9",
				},
				timeout: {
					type: "number",
					title: "Timeout",
					description: "Timeout in seconds",
					default: 300,
				},
				debug: {
					type: "boolean",
					title: "Debug Mode",
					default: false,
				},
			},
		},
		data: {},
	},
};

export const NestedObject: Story = {
	args: {
		schema: {
			properties: {
				env: {
					type: "object",
					title: "Environment Variables",
					description: "Environment variables to set",
				},
				resources: {
					type: "object",
					title: "Resource Limits",
					description: "CPU and memory limits",
				},
			},
		},
		data: {
			env: {
				NODE_ENV: "production",
				DEBUG: "false",
				API_URL: "https://api.example.com",
			},
			resources: {
				cpu: "1000m",
				memory: "512Mi",
				storage: "10Gi",
			},
		},
	},
};

export const ComplexArray: Story = {
	args: {
		schema: {
			properties: {
				volumes: {
					type: "array",
					title: "Volumes",
					description: "Volume mounts",
					items: { type: "object" },
				},
				ports: {
					type: "array",
					title: "Ports",
					description: "Port mappings",
					items: { type: "number" },
				},
			},
		},
		data: {
			volumes: [
				{ name: "data", mountPath: "/data", size: "10Gi" },
				{ name: "logs", mountPath: "/var/log", size: "1Gi" },
			],
			ports: [8080, 8443, 9090],
		},
	},
};

export const EmptySchema: Story = {
	args: {
		schema: {},
		data: {},
	},
};

export const EmptyProperties: Story = {
	args: {
		schema: {
			properties: {},
		},
		data: {},
	},
};

export const WorkPoolJobTemplate: Story = {
	args: {
		schema: {
			properties: {
				image: {
					type: "string",
					title: "Docker Image",
					description: "The Docker image to use for the job",
					default: "python:3.9",
				},
				command: {
					type: "array",
					title: "Command",
					description: "Command to run in the container",
					items: { type: "string" },
					default: ["python", "-m", "prefect.engine"],
				},
				env: {
					type: "object",
					title: "Environment Variables",
					description: "Environment variables to set in the container",
					default: {},
				},
				cpu: {
					type: "string",
					title: "CPU Request",
					description: "CPU resources to request",
					default: "100m",
				},
				memory: {
					type: "string",
					title: "Memory Request",
					description: "Memory resources to request",
					default: "128Mi",
				},
			},
		},
		data: {
			image: "prefecthq/prefect:2.0.0",
			command: ["python", "main.py"],
			env: {
				PREFECT_API_URL: "https://api.prefect.cloud",
				PREFECT_WORKSPACE: "my-workspace",
			},
			cpu: "500m",
			memory: "1Gi",
		},
	},
};
