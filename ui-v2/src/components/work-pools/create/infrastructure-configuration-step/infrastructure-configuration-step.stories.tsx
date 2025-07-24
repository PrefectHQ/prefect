import type { Meta, StoryObj } from "@storybook/react";
import { FormProvider, useForm } from "react-hook-form";
import { InfrastructureConfigurationStep } from "./infrastructure-configuration-step";

function DefaultStory() {
	const form = useForm({
		defaultValues: {
			type: "kubernetes",
			baseJobTemplate: {
				job_configuration: {
					apiVersion: "batch/v1",
					kind: "Job",
					spec: {
						template: {
							spec: {
								containers: [
									{
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
							title: "CPU Cores",
						},
						memory: {
							type: "string",
							default: "1Gi",
							title: "Memory",
						},
					},
				},
			},
		},
	});

	return (
		<div className="max-w-4xl mx-auto p-6">
			<FormProvider {...form}>
				<InfrastructureConfigurationStep />
			</FormProvider>
		</div>
	);
}

function EmptySchemaStory() {
	const form = useForm({
		defaultValues: {
			type: "process",
			baseJobTemplate: {
				job_configuration: {},
				variables: {
					type: "object",
					properties: {},
				},
			},
		},
	});

	return (
		<div className="max-w-4xl mx-auto p-6">
			<FormProvider {...form}>
				<InfrastructureConfigurationStep />
			</FormProvider>
		</div>
	);
}

function NoBaseJobTemplateStory() {
	const form = useForm({
		defaultValues: {
			type: "docker",
		},
	});

	return (
		<div className="max-w-4xl mx-auto p-6">
			<FormProvider {...form}>
				<InfrastructureConfigurationStep />
			</FormProvider>
		</div>
	);
}

function ComplexSchemaStory() {
	const form = useForm({
		defaultValues: {
			type: "kubernetes",
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
		},
	});

	return (
		<div className="max-w-4xl mx-auto p-6">
			<FormProvider {...form}>
				<InfrastructureConfigurationStep />
			</FormProvider>
		</div>
	);
}

const meta = {
	title: "Components/WorkPools/Create/Infrastructure Configuration Step",
	component: InfrastructureConfigurationStep,
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof InfrastructureConfigurationStep>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	render: () => <DefaultStory />,
};

export const EmptySchema: Story = {
	render: () => <EmptySchemaStory />,
};

export const NoBaseJobTemplate: Story = {
	render: () => <NoBaseJobTemplateStory />,
};

export const ComplexSchema: Story = {
	render: () => <ComplexSchemaStory />,
};
