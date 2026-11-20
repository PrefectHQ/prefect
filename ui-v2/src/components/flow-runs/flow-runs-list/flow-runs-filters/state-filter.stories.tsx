import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { StateFilter } from "./state-filter";

const meta: Meta<typeof StateFilter> = {
	title: "Components/FlowRuns/StateFilter",
	decorators: [reactQueryDecorator],
	component: StateFilterStory,
};
export default meta;

function StateFilterStory() {
	const [filters, setFilters] = useState<Set<string>>();
	return <StateFilter selectedFilters={filters} onSelectFilter={setFilters} />;
}

export const story: StoryObj = { name: "StateFilter" };
