import { FlowRunWithDeploymentAndFlow } from "@/api/flow-runs";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { DeploymentsDataTable } from ".";

const createFakeFlowRunWithDeploymentAndFlow =
	(): FlowRunWithDeploymentAndFlow => {
		const flowRun = createFakeFlowRun();

		return {
			...flowRun,
			deployment: createFakeDeployment(),
			flow: createFakeFlow(),
		};
	};

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof DeploymentsDataTable>;

export const Default: StoryObj = {
	name: "Randomized Data",
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), async ({ request }) => {
					const { limit } = (await request.json()) as { limit: number };

					return HttpResponse.json(
						Array.from(
							{ length: limit },
							createFakeFlowRunWithDeploymentAndFlow,
						),
					);
				}),
			],
		},
	},
	args: {
		deployments: Array.from({ length: 10 }, createFakeDeployment),
		onQuickRun: fn(),
		onCustomRun: fn(),
		onEdit: fn(),
		onDelete: fn(),
		onDuplicate: fn(),
	},
};

export const Empty: StoryObj = {
	name: "Empty",
	args: {
		deployments: [],
	},
};
