import type { Meta, StoryObj } from "@storybook/react";

import { useState } from "react";
import { createFakeFlowRunName } from "./create-fake-flow-run-name";
import { FlowRunNameInput } from "./flow-run-name-input";

const meta = {
	title: "Components/Deployments/CreateFlowRunForm/FlowRunNameInput",
	component: FlowRunNameInputStory,
} satisfies Meta<typeof FlowRunNameInput>;

export default meta;

function FlowRunNameInputStory() {
	const [flowName, setFlowName] = useState(createFakeFlowRunName());

	return (
		<FlowRunNameInput
			onClickGenerate={setFlowName}
			value={flowName}
			onChange={(e) => setFlowName(e.target.value)}
		/>
	);
}

export const Story: StoryObj = {
	name: "FlowRunNameInput",
};
