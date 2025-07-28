import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { BaseJobTemplateFormSection } from "./base-job-template-form-section";
import type { WorkerBaseJobTemplate } from "./schema";

const meta = {
	title: "Components/WorkPools/Create/Base Job Template Form Section",
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
		spec: {
			template: {
				spec: {
					containers: [
						{
							image: "{{ image }}",
							resources: {
								requests: {
									cpu: "{{ cpu }}",
									memory: "{{ memory }}",
								},
							},
						},
					],
				},
			},
		},
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
		onBaseJobTemplateChange: fn(),
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
		onBaseJobTemplateChange: fn(),
	},
};

export const NoVariables: Story = {
	args: {
		baseJobTemplate: {
			job_configuration: {
				command: "echo 'Hello World'",
			},
			variables: {
				type: "object",
				properties: {},
			},
		},
		onBaseJobTemplateChange: fn(),
	},
};

export const ComplexSchema: Story = {
	args: {
		baseJobTemplate: {
			job_configuration: {
				apiVersion: "batch/v1",
				kind: "Job",
				metadata: {
					namespace: "{{ namespace }}",
					labels: "{{ labels }}",
				},
				spec: {
					template: {
						spec: {
							containers: [
								{
									image: "{{ image }}",
									env: "{{ env }}",
									resources: {
										requests: {
											cpu: "{{ cpu }}",
											memory: "{{ memory }}",
										},
									},
								},
							],
							tolerations: "{{ tolerations }}",
						},
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
		onBaseJobTemplateChange: fn(),
	},
};
