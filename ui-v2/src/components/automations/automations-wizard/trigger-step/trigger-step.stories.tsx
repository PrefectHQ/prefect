import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerStep } from "./trigger-step";

const meta = {
	title: "Components/Automations/Wizard/TriggerStep",
	component: TriggerStep,
	decorators: [reactQueryDecorator, routerDecorator],
	render: TriggerStepStory,
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "TriggerStep" };

function TriggerStepStory() {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[600px] p-6">
					<TriggerStep />
				</Card>
			</form>
		</Form>
	);
}
