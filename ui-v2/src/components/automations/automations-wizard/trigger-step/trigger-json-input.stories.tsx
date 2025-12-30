import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerJsonInput } from "./trigger-json-input";

const meta = {
	title: "Components/Automations/Wizard/TriggerJsonInput",
	component: TriggerJsonInput,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof TriggerJsonInput>;

export default meta;

type Story = StoryObj<typeof meta>;

const validTriggerExample = {
	type: "event",
	posture: "Reactive",
	threshold: 1,
	within: 0,
	expect: ["prefect.flow-run.Completed"],
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
};

function TriggerJsonInputStory({
	defaultValue = "",
	error,
}: {
	defaultValue?: string;
	error?: string;
}) {
	const [value, setValue] = useState(defaultValue);

	return (
		<Card className="w-[600px] p-6">
			<TriggerJsonInput value={value} onChange={setValue} error={error} />
		</Card>
	);
}

export const Empty: Story = {
	render: () => <TriggerJsonInputStory />,
};

export const ValidTrigger: Story = {
	render: () => (
		<TriggerJsonInputStory
			defaultValue={JSON.stringify(validTriggerExample, null, 2)}
		/>
	),
};

export const InvalidJSON: Story = {
	render: () => <TriggerJsonInputStory defaultValue="{ invalid json" />,
};

export const WithExternalError: Story = {
	render: () => (
		<TriggerJsonInputStory error="External validation error from form" />
	),
};

export const UnformattedJSON: Story = {
	render: () => (
		<TriggerJsonInputStory defaultValue='{"type":"event","posture":"Reactive","threshold":1,"within":0}' />
	),
};

export const CompoundTrigger: Story = {
	render: () => (
		<TriggerJsonInputStory
			defaultValue={JSON.stringify(
				{
					type: "compound",
					require: "all",
					within: 60,
					triggers: [
						{
							type: "event",
							posture: "Reactive",
							threshold: 1,
							within: 0,
							expect: ["prefect.flow-run.Completed"],
						},
						{
							type: "event",
							posture: "Reactive",
							threshold: 1,
							within: 0,
							expect: ["prefect.flow-run.Failed"],
						},
					],
				},
				null,
				2,
			)}
		/>
	),
};
