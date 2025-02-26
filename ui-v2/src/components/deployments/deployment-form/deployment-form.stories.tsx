import {
	createFakeDeployment,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { DeploymentForm } from "./deployment-form";

const MOCK_WORK_POOLS_DATA = Array.from({ length: 5 }, createFakeWorkPool);
const MOCK_WORK_QUEUES_DATA = Array.from({ length: 5 }, () =>
	createFakeWorkQueue({ work_pool_name: "my-work-pool" }),
);
const meta = {
	title: "Components/Deployments/DeploymentForm",
	decorators: [routerDecorator, toastDecorator, reactQueryDecorator],
	component: DeploymentForm,
	args: { deployment: createFakeDeployment() },
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
				http.patch(buildApiUrl("/deployments/id"), () => {
					return HttpResponse.json(createFakeDeployment());
				}),
			],
		},
	},
} satisfies Meta<typeof DeploymentForm>;

export default meta;

export const story: StoryObj = {
	name: "DeploymentForm",
};
