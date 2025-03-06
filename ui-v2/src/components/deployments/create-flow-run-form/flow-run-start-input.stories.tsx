import type { Meta, StoryObj } from "@storybook/react";

import { useState } from "react";
import { FlowRunStartInput } from "./flow-run-start-input";

const meta = {
	title: "Components/Deployments/CreateFlowRunForm/FlowRunStartInput",
	component: FlowRunStartInputStory,
} satisfies Meta<typeof FlowRunStartInput>;

export default meta;

function FlowRunStartInputStory() {
	const [startDate, setStartDate] = useState<string | null>(null);

	return <FlowRunStartInput value={startDate} onValueChange={setStartDate} />;
}

export const Story: StoryObj = {
	name: "FlowRunStartInput",
};
