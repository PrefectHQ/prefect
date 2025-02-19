import type { Meta, StoryObj } from "@storybook/react";

import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import { routerDecorator } from "@/storybook/utils";
import { FlowRunsDataTable } from "./data-table";

const MOCK_DATA = Array.from(
	{ length: 5 },
	createFakeFlowRunWithDeploymentAndFlow,
);

const meta: Meta<typeof FlowRunsDataTable> = {
	title: "Components/FlowRuns/DataTable/FlowRunsDataTable",
	decorators: [routerDecorator],
	args: { flowRuns: MOCK_DATA, flowRunsCount: MOCK_DATA.length },
	component: FlowRunsDataTable,
};
export default meta;

export const story: StoryObj = { name: "FlowRunsDataTable" };
