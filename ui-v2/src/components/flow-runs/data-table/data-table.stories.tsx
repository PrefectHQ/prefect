import type { Meta, StoryObj } from "@storybook/react";

import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { faker } from "@faker-js/faker";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { FlowRunsDataTable } from "./data-table";

const MOCK_DATA = [
	createFakeFlowRunWithDeploymentAndFlow({
		id: "0",
		state: { type: "SCHEDULED", id: "0" },
	}),
	createFakeFlowRunWithDeploymentAndFlow({ id: "1" }),
	createFakeFlowRunWithDeploymentAndFlow({ id: "2" }),
	createFakeFlowRunWithDeploymentAndFlow({ id: "3" }),
	createFakeFlowRunWithDeploymentAndFlow({ id: "4" }),
];

const MOCK_FLOW_RUNS_TASK_COUNT = {
	"0": faker.number.int({ min: 0, max: 5 }),
	"1": faker.number.int({ min: 0, max: 5 }),
	"2": faker.number.int({ min: 0, max: 5 }),
	"3": faker.number.int({ min: 0, max: 5 }),
	"4": faker.number.int({ min: 0, max: 5 }),
};

const meta: Meta<typeof FlowRunsDataTable> = {
	title: "Components/FlowRuns/DataTable/FlowRunsDataTable",
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	args: { flowRuns: MOCK_DATA, flowRunsCount: MOCK_DATA.length },
	component: FlowRunsDataTable,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS_TASK_COUNT);
				}),
			],
		},
	},
};
export default meta;

export const story: StoryObj = { name: "FlowRunsDataTable" };
