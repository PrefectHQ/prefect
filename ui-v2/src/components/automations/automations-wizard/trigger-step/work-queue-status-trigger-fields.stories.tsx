import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkQueueStatusTriggerFields } from "./work-queue-status-trigger-fields";

const meta = {
	title: "Components/Automations/Wizard/WorkQueueStatusTriggerFields",
	component: WorkQueueStatusTriggerFields,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof WorkQueueStatusTriggerFields>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <WorkQueueStatusTriggerFieldsStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <WorkQueueStatusTriggerFieldsStory posture="Proactive" />,
};

export const WithReadyStatus: Story = {
	render: () => (
		<WorkQueueStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-queue.ready"
		/>
	),
};

export const WithNotReadyStatus: Story = {
	render: () => (
		<WorkQueueStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-queue.not-ready"
		/>
	),
};

export const WithPausedStatus: Story = {
	render: () => (
		<WorkQueueStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-queue.paused"
		/>
	),
};

function WorkQueueStatusTriggerFieldsStory({
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
					<WorkQueueStatusTriggerFields />
				</Card>
			</form>
		</Form>
	);
}
