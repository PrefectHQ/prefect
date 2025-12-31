import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import {
	AutomationWizardSchema,
	type TriggerTemplate,
} from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerStep } from "./trigger-step";
import { getDefaultTriggerForTemplate } from "./trigger-step-utils";

const meta = {
	title: "Components/Automations/Wizard/TriggerStep",
	component: TriggerStep,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
	name: "TriggerStep",
	render: () => <TriggerStepStory />,
};

export const FormMode: Story = {
	name: "Form Mode (with template selected)",
	render: () => <TriggerStepStory initialTemplate="flow-run-state" />,
};

export const WithDeploymentStatusTemplate: Story = {
	name: "Deployment Status Template",
	render: () => <TriggerStepStory initialTemplate="deployment-status" />,
};

export const WithWorkPoolStatusTemplate: Story = {
	name: "Work Pool Status Template",
	render: () => <TriggerStepStory initialTemplate="work-pool-status" />,
};

export const WithCustomTemplate: Story = {
	name: "Custom Template",
	render: () => <TriggerStepStory initialTemplate="custom" />,
};

type TriggerStepStoryProps = {
	initialTemplate?: TriggerTemplate;
};

function TriggerStepStory({ initialTemplate }: TriggerStepStoryProps = {}) {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			triggerTemplate: initialTemplate,
			trigger: initialTemplate
				? getDefaultTriggerForTemplate(initialTemplate)
				: {
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
