import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import {
	createFakeDeployment,
	createFakeFlowRun,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { CreateFlowRunForm } from "./create-flow-run-form";

const MOCK_WORK_POOLS_DATA = Array.from({ length: 5 }, createFakeWorkPool);
const MOCK_WORK_QUEUES_DATA = Array.from({ length: 5 }, () =>
	createFakeWorkQueue({ work_pool_name: "my-work-pool" }),
);
const meta = {
	title: "Components/Deployments/CreateFlowRunForm",
	decorators: [routerDecorator, toastDecorator, reactQueryDecorator],
	component: CreateFlowRunForm,
	args: {
		deployment: createFakeDeployment({ work_pool_name: "my-work-pool" }),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(MOCK_WORK_POOLS_DATA);
				}),
				http.post(
					buildApiUrl("/work_pools/:work_pool_name/queues/filter"),
					() => {
						return HttpResponse.json(MOCK_WORK_QUEUES_DATA);
					},
				),
				http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
					return HttpResponse.json(createFakeFlowRun());
				}),
			],
		},
	},
} satisfies Meta<typeof CreateFlowRunForm>;

export default meta;

export const Story: StoryObj = {
	name: "CreateFlowRunForm",
};
