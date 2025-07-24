import type { Meta, StoryObj } from "@storybook/react";
import { FormProvider, useForm } from "react-hook-form";
import { InfrastructureConfigurationStep } from "./infrastructure-configuration-step";

function DefaultStory() {
	const form = useForm({
		defaultValues: {
			type: "kubernetes",
			baseJobTemplate: {
				job_configuration: {},
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

function PrefectAgentStory() {
	const form = useForm({
		defaultValues: {
			type: "prefect-agent",
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
	title: "Components/Work Pools/Create/Infrastructure Configuration Step",
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

export const PrefectAgent: Story = {
	render: () => <PrefectAgentStory />,
};
