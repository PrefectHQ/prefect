import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import type { StateType } from "@/api/flow-runs/constants";
import { StateTypeFilter } from "./state-type-filter";

const meta = {
	title: "Components/FlowRuns/StateTypeFilter",
	component: StateTypeFilter,
} satisfies Meta<typeof StateTypeFilter>;
export default meta;
export const Default: StoryObj = {
	render: function Render() {
		const [types, setTypes] = useState<Set<StateType>>(new Set(["FAILED"]));
		return (
			<StateTypeFilter selectedFilters={types} onSelectFilter={setTypes} />
		);
	},
};
