import type { Meta, StoryObj } from "@storybook/react";

import { useState } from "react";
import { type FlowRunState, StateFilter } from "./state-filter";

const meta: Meta<typeof StateFilter> = {
	title: "Components/FlowRuns/DataTable/StateFilter",
	component: StateFilterStory,
};
export default meta;

function StateFilterStory() {
	const [filters, setFilters] = useState<Set<FlowRunState>>();
	return <StateFilter selectedFilters={filters} onSelectFilter={setFilters} />;
}

export const story: StoryObj = { name: "StateFilter" };
