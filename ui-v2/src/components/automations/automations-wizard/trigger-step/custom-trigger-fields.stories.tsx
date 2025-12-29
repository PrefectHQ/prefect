import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { CustomTriggerFields } from "./custom-trigger-fields";

const meta = {
	title: "Components/Automations/Wizard/CustomTriggerFields",
	component: CustomTriggerFields,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof CustomTriggerFields>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <CustomTriggerFieldsStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <CustomTriggerFieldsStory posture="Proactive" />,
};

export const WithEvents: Story = {
	render: () => (
		<CustomTriggerFieldsStory
			posture="Reactive"
			events={["prefect.flow-run.Completed", "prefect.flow-run.Failed"]}
		/>
	),
};

function CustomTriggerFieldsStory({
	posture = "Reactive",
	events = [],
}: {
	posture?: "Reactive" | "Proactive";
	events?: string[];
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
				expect: events.length > 0 ? events : [],
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[600px] p-6">
					<CustomTriggerFields />
				</Card>
			</form>
		</Form>
	);
}
