import { randNumber } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import {
	createFakeFlowRunWithDeploymentAndFlow,
	createFakeFlowRunWithFlow,
} from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunCard } from "./flow-run-card";

const MOCK_DATA = createFakeFlowRunWithFlow({
	id: "0",
});
const MOCK_DATA_WITH_DEPLOYMENT = createFakeFlowRunWithDeploymentAndFlow({
	id: "0",
});
const MOCK_FLOW_RUNS_TASK_COUNT = {
	"0": randNumber({ min: 0, max: 5 }),
};

const meta = {
	title: "Components/FlowRuns/FlowRunCard",
	component: FlowRunCard,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS_TASK_COUNT);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunCard>;

export default meta;
type Story = StoryObj<typeof FlowRunCard>;

export const Selectable: Story = {
	args: { flowRun: MOCK_DATA, checked: true, onCheckedChange: fn() },
};
export const ViewOnly: Story = {
	args: { flowRun: MOCK_DATA },
};
export const WithDeployment: Story = {
	args: { flowRun: MOCK_DATA_WITH_DEPLOYMENT },
};
