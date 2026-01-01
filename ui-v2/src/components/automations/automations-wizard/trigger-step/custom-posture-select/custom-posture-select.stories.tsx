import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { CustomPostureSelect } from "./index";

const meta = {
	title: "Components/Automations/Wizard/CustomPostureSelect",
	component: CustomPostureSelect,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof CustomPostureSelect>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Reactive: Story = {
	render: () => <CustomPostureSelectStory posture="Reactive" />,
};

export const Proactive: Story = {
	render: () => <CustomPostureSelectStory posture="Proactive" />,
};

export const ReactiveWithExpectValues: Story = {
	render: () => (
		<CustomPostureSelectStory
			posture="Reactive"
			expect={["prefect.flow-run.Completed", "prefect.flow-run.Failed"]}
		/>
	),
};

export const ProactiveWithAfterValues: Story = {
	render: () => (
		<CustomPostureSelectStory
			posture="Proactive"
			after={["prefect.flow-run.Pending"]}
			within={60}
		/>
	),
};

function CustomPostureSelectStory({
	posture = "Reactive",
	expect = [],
	after = [],
	within,
}: {
	posture?: "Reactive" | "Proactive";
	expect?: string[];
	after?: string[];
	within?: number;
}) {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture,
				threshold: 1,
				within: within ?? (posture === "Proactive" ? 30 : 0),
				expect: posture === "Reactive" ? expect : [],
				after: posture === "Proactive" ? after : [],
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<Card className="w-[400px] p-6">
					<CustomPostureSelect />
				</Card>
			</form>
		</Form>
	);
}
