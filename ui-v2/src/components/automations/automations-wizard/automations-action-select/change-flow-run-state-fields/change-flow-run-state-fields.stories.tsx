import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import {
	ChangeFlowRunStateFields,
	type ChangeFlowRunStateFields as TChangeFlowRunStateFields,
} from "./change-flow-run-state-fields";

const meta = {
	title: "Components/Automations/Wizard/ChangeFlowRunStateFields",
	component: ChangeFlowRunStateFields,
	render: function ComponentExmaple() {
		const [values, setValues] = useState<TChangeFlowRunStateFields>({});
		return <ChangeFlowRunStateFields values={values} onChange={setValues} />;
	},
} satisfies Meta<typeof ChangeFlowRunStateFields>;

export default meta;

export const story: StoryObj = { name: "ChangeFlowRunStateFields" };
