import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import {
	createFakeAutomation,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { AutomationWizard } from "./automation-wizard";

const MOCK_AUTOMATIONS_DATA = Array.from({ length: 5 }, createFakeAutomation);
const MOCK_DEPLOYMENTS_WITH_FLOW_A = Array.from({ length: 2 }, () =>
	createFakeDeployment({ flow_id: "a" }),
);
const MOCK_DEPLOYMENTS_WITH_FLOW_B = Array.from({ length: 3 }, () =>
	createFakeDeployment({ flow_id: "b" }),
);
const MOCK_FLOWS_DATA = [
	createFakeFlow({ id: "a" }),
	createFakeFlow({ id: "b" }),
];
const MOCK_WORK_POOLS_DATA = Array.from({ length: 5 }, createFakeWorkPool);

const MOCK_WORK_QUEUES_DATA = [
	createFakeWorkQueue({ work_pool_name: "My workpool A" }),
	createFakeWorkQueue({ work_pool_name: "My workpool A" }),
	createFakeWorkQueue({ work_pool_name: "My workpool A" }),
	createFakeWorkQueue({ work_pool_name: "My workpool B" }),
	createFakeWorkQueue({ work_pool_name: "My workpool B" }),
];

const meta = {
	title: "Components/Automations/Wizard/AutomationWizard",
	component: AutomationWizard,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(MOCK_AUTOMATIONS_DATA);
				}),
				http.post(buildApiUrl("/deployments/paginate"), () => {
					return HttpResponse.json({
						count: 5,
						limit: 100,
						page: 1,
						pages: 1,
						results: [
							...MOCK_DEPLOYMENTS_WITH_FLOW_A,
							...MOCK_DEPLOYMENTS_WITH_FLOW_B,
						],
					});
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS_DATA);
				}),
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(MOCK_WORK_POOLS_DATA);
				}),
				http.post(buildApiUrl("/work_queues/filter"), () => {
					return HttpResponse.json(MOCK_WORK_QUEUES_DATA);
				}),
			],
		},
	},
} satisfies Meta<typeof AutomationWizard>;

export default meta;

type Story = StoryObj<typeof AutomationWizard>;

export const CreateAutomation: Story = {};
