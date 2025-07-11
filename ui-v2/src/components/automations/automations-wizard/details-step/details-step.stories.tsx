import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { fn } from "storybook/test";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { DetailsStep } from "./details-step";

const meta = {
	title: "Components/Automations/Wizard/DetailsStep",
	component: DetailsStep,
	args: { onPrevious: fn(), onSave: fn() },
	render: DetailsStepsStory,
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "DetailsStep" };

function DetailsStepsStory() {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: { actions: [{ type: undefined }] },
	});

	return (
		<Form {...form}>
			<form>
				<DetailsStep />
			</form>
		</Form>
	);
}
