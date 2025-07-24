import type { Meta, StoryObj } from "@storybook/react";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";
import type { WorkerBaseJobTemplate } from "./schema";

const meta = {
	title: "Components/Work Pools/Create/Base Job Template Form Section",
	component: BaseJobTemplateFormSection,
	parameters: {
		layout: "padded",
	},
} satisfies Meta<typeof BaseJobTemplateFormSection>;

export default meta;
type Story = StoryObj<typeof meta>;

const mockBaseJobTemplate: WorkerBaseJobTemplate = {
	job_configuration: {
		apiVersion: "batch/v1",
		kind: "Job",
	},
	variables: {
		type: "object",
		properties: {
			cpu: {
				type: "number",
				default: 1,
				minimum: 0.1,
				maximum: 16,
				title: "CPU Cores",
				description: "Number of CPU cores to allocate to the pod",
			},
			memory: {
				type: "string",
				default: "1Gi",
				title: "Memory",
				description: "Amount of memory to allocate to the pod",
			},
			image: {
				type: "string",
				default: "prefecthq/prefect:2-latest",
				title: "Container Image",
				description: "Docker image to use for the job",
			},
		},
	},
};

export const Default: Story = {
	args: {
		baseJobTemplate: mockBaseJobTemplate,
		onBaseJobTemplateChange: () => {},
	},
};

export const EmptySchema: Story = {
	args: {
		baseJobTemplate: {
			job_configuration: {},
			variables: {
				type: "object",
				properties: {},
			},
		},
		onBaseJobTemplateChange: () => {},
	},
};

export const NoVariables: Story = {
	args: {
		baseJobTemplate: {
			job_configuration: {
				command: "echo 'Hello World'",
			},
		},
		onBaseJobTemplateChange: () => {},
	},
};

export const ComplexSchema: Story = {
	args: {
		baseJobTemplate: {
			job_configuration: {
				apiVersion: "batch/v1",
				kind: "Job",
				metadata: {
					labels: {
						app: "prefect-flow",
					},
				},
			},
			variables: {
				type: "object",
				properties: {
					cpu: {
						type: "number",
						default: 2,
						minimum: 0.1,
						maximum: 16,
						title: "CPU Cores",
						description: "Number of CPU cores to allocate to the pod",
					},
					memory: {
						type: "string",
						default: "2Gi",
						title: "Memory",
						description: "Amount of memory to allocate to the pod",
					},
					image: {
						type: "string",
						default: "prefecthq/prefect:2-latest",
						title: "Container Image",
						description: "Docker image to use for the job",
					},
					namespace: {
						type: "string",
						default: "default",
						title: "Namespace",
						description: "Kubernetes namespace to run the job in",
					},
					env: {
						type: "object",
						default: {},
						title: "Environment Variables",
						description: "Environment variables to set in the container",
						additionalProperties: {
							type: "string",
						},
					},
					labels: {
						type: "object",
						default: {},
						title: "Pod Labels",
						description: "Labels to apply to the pod",
						additionalProperties: {
							type: "string",
						},
					},
					tolerations: {
						type: "array",
						default: [],
						title: "Tolerations",
						description: "Tolerations to apply to the pod",
						items: {
							type: "object",
							properties: {
								key: { type: "string" },
								operator: { type: "string" },
								value: { type: "string" },
								effect: { type: "string" },
							},
						},
					},
				},
			},
		},
		onBaseJobTemplateChange: () => {},
	},
};
