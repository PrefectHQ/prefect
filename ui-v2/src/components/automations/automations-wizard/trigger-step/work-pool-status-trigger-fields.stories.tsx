import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolStatusTriggerFields } from "./work-pool-status-trigger-fields";

const meta = {
	title: "Components/Automations/Wizard/WorkPoolStatusTriggerFields",
	component: WorkPoolStatusTriggerFields,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof WorkPoolStatusTriggerFields>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <WorkPoolStatusTriggerFieldsStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <WorkPoolStatusTriggerFieldsStory posture="Proactive" />,
};

export const WithReadyStatus: Story = {
	render: () => (
		<WorkPoolStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-pool.ready"
		/>
	),
};

export const WithNotReadyStatus: Story = {
	render: () => (
		<WorkPoolStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-pool.not-ready"
		/>
	),
};

export const WithPausedStatus: Story = {
	render: () => (
		<WorkPoolStatusTriggerFieldsStory
			posture="Reactive"
			selectedStatus="prefect.work-pool.paused"
		/>
	),
};

function WorkPoolStatusTriggerFieldsStory({
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
				match: {
					"prefect.resource.id": "prefect.work-pool.*",
				},
				for_each: ["prefect.resource.id"],
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[600px] p-6">
					<WorkPoolStatusTriggerFields />
				</Card>
			</form>
		</Form>
	);
}
