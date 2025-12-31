import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { DeploymentStatusTriggerFields } from "./deployment-status-trigger-fields";

const meta = {
	title: "Components/Automations/Wizard/DeploymentStatusTriggerFields",
	component: DeploymentStatusTriggerFields,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof DeploymentStatusTriggerFields>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <DeploymentStatusTriggerFieldsStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <DeploymentStatusTriggerFieldsStory posture="Proactive" />,
};

export const WithReadyStatus: Story = {
	render: () => (
		<DeploymentStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.deployment.ready"
		/>
	),
};

export const WithNotReadyStatus: Story = {
	render: () => (
		<DeploymentStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.deployment.not-ready"
		/>
	),
};

export const WithDisabledStatus: Story = {
	render: () => (
		<DeploymentStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.deployment.disabled"
		/>
	),
};

function DeploymentStatusTriggerFieldsStory({
	posture = "Reactive",
	selectedStatus,
}: {
	posture?: "Reactive" | "Proactive";
	selectedStatus?: string;
}) {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture,
				threshold: 1,
				within: posture === "Proactive" ? 30 : 0,
				expect: selectedStatus ? [selectedStatus] : [],
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[600px] p-6">
					<DeploymentStatusTriggerFields />
				</Card>
			</form>
		</Form>
	);
}
