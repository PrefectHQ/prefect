import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { delay, HttpResponse, http } from "msw";
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

const baseHandlers = [
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
];

const meta = {
	title: "Components/Automations/Wizard/AutomationWizard",
	component: AutomationWizard,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				...baseHandlers,
				http.post(buildApiUrl("/automations/"), () => {
					return HttpResponse.json(createFakeAutomation(), { status: 201 });
				}),
			],
		},
	},
} satisfies Meta<typeof AutomationWizard>;

export default meta;

type Story = StoryObj<typeof AutomationWizard>;

export const Default: Story = {
	name: "Default (Trigger Step)",
};

export const SubmissionLoading: Story = {
	name: "Submission Loading State",
	parameters: {
		docs: {
			description: {
				story:
					"Shows the loading state when submitting the form. Navigate to the Details step, fill in the name, and click Save to see the loading state.",
			},
		},
		msw: {
			handlers: [
				...baseHandlers,
				http.post(buildApiUrl("/automations/"), async () => {
					await delay(5000);
					return HttpResponse.json(createFakeAutomation(), { status: 201 });
				}),
			],
		},
	},
};

export const SubmissionError: Story = {
	name: "Submission Error State",
	parameters: {
		docs: {
			description: {
				story:
					"Shows the error state when submission fails. Navigate to the Details step, fill in the name, and click Save to see the error toast.",
			},
		},
		msw: {
			handlers: [
				...baseHandlers,
				http.post(buildApiUrl("/automations/"), () => {
					return HttpResponse.json(
						{
							detail:
								"Failed to create automation: Invalid trigger configuration",
						},
						{ status: 422 },
					);
				}),
			],
		},
	},
};

export const SubmissionSuccess: Story = {
	name: "Submission Success State",
	parameters: {
		docs: {
			description: {
				story:
					"Shows the success state when submission succeeds. Navigate to the Details step, fill in the name, and click Save to see the success toast and navigation.",
			},
		},
		msw: {
			handlers: [
				...baseHandlers,
				http.post(buildApiUrl("/automations/"), async () => {
					await delay(500);
					return HttpResponse.json(createFakeAutomation(), { status: 201 });
				}),
			],
		},
	},
};
