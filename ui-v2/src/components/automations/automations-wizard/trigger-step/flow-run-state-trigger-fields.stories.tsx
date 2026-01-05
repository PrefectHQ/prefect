import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import type { StateName } from "@/api/flow-runs/constants";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";

const meta = {
	title: "Components/Automations/Wizard/FlowRunStateTriggerFields",
	component: FlowRunStateTriggerFields,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof FlowRunStateTriggerFields>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <FlowRunStateTriggerFieldsStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <FlowRunStateTriggerFieldsStory posture="Proactive" />,
};

export const ProactiveWithMinutes: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory posture="Proactive" within={120} />
	),
};

export const ProactiveWithHours: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory posture="Proactive" within={7200} />
	),
};

export const WithSelectedStates: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory
			posture="Reactive"
			selectedStates={["Completed", "Failed"]}
		/>
	),
};

export const WithAllExceptScheduled: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory
			posture="Reactive"
			selectedStates={[
				"Late",
				"Resuming",
				"AwaitingRetry",
				"AwaitingConcurrencySlot",
				"Pending",
				"Paused",
				"Suspended",
				"Running",
				"Retrying",
				"Completed",
				"Cached",
				"Cancelled",
				"Cancelling",
				"Crashed",
				"Failed",
				"TimedOut",
			]}
		/>
	),
};

export const WithSelectedFlows: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory
			posture="Reactive"
			selectedFlowIds={["flow-id-1", "flow-id-2"]}
		/>
	),
};

export const WithSelectedTags: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory
			posture="Reactive"
			selectedTags={["production", "critical"]}
		/>
	),
};

export const WithFlowsHidesTags: Story = {
	render: () => (
		<FlowRunStateTriggerFieldsStory
			posture="Reactive"
			selectedFlowIds={["flow-id-1"]}
			selectedStates={["Completed"]}
		/>
	),
};

function FlowRunStateTriggerFieldsStory({
	posture = "Reactive",
	selectedStates = [],
	selectedFlowIds = [],
	selectedTags = [],
	within,
}: {
	posture?: "Reactive" | "Proactive";
	selectedStates?: StateName[];
	selectedFlowIds?: string[];
	selectedTags?: string[];
	within?: number;
}) {
	const buildMatchRelated = () => {
		const resourceIds: string[] = [
			...selectedFlowIds.map((id) => `prefect.flow.${id}`),
			...selectedTags.map((tag) => `prefect.tag.${tag}`),
		];

		if (resourceIds.length === 0) {
			return undefined;
		}

		return {
			"prefect.resource.role": "flow",
			"prefect.resource.id": resourceIds,
		};
	};

	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture,
				threshold: 1,
				within: within ?? (posture === "Proactive" ? 30 : 0),
				expect: posture === "Reactive" ? selectedStates : [],
				after: posture === "Proactive" ? selectedStates : [],
				match_related: buildMatchRelated(),
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[600px] p-6">
					<FlowRunStateTriggerFields />
				</Card>
			</form>
		</Form>
	);
}
