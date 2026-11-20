import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import { createFakeDeployment, createFakeFlow } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowPageHeader } from "./flow-page-header";

const meta = {
	title: "Components/Flows/FlowPageHeader",
	component: FlowPageHeader,
	decorators: [reactQueryDecorator, toastDecorator, routerDecorator],
	args: {
		onDelete: fn(),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(
					buildApiUrl("/ui/flows/count-deployments"),
					async ({ request }) => {
						const body = (await request.json()) as {
							flow_ids: string[];
						};
						return HttpResponse.json(
							Object.fromEntries(body.flow_ids.map((id) => [id, 1])),
						);
					},
				),
				http.post(buildApiUrl("/deployments/paginate"), async ({ request }) => {
					const body = (await request.json()) as {
						flows?: { id?: { any_?: string[] } };
					};
					const flowId = body.flows?.id?.any_?.[0];
					return HttpResponse.json({
						results: [
							createFakeDeployment({
								flow_id: flowId,
								name: "my-deployment",
							}),
						],
						count: 1,
						page: 1,
						pages: 1,
						limit: 10,
					});
				}),
			],
		},
	},
} satisfies Meta<typeof FlowPageHeader>;

export default meta;
type Story = StoryObj<typeof FlowPageHeader>;

export const Default: Story = {
	args: {
		flow: createFakeFlow({
			name: "my-etl-flow",
		}),
	},
};

export const LongFlowName: Story = {
	args: {
		flow: createFakeFlow({
			name: "my-very-long-flow-name-that-might-cause-wrapping-issues-in-the-breadcrumb",
		}),
	},
};

export const FlowWithTags: Story = {
	args: {
		flow: createFakeFlow({
			name: "tagged-flow",
			tags: ["production", "etl", "daily"],
		}),
	},
};

export const FlowWithLabels: Story = {
	args: {
		flow: createFakeFlow({
			name: "labeled-flow",
			labels: { environment: "production", team: "data-engineering" },
		}),
	},
};

export const SimpleFlowName: Story = {
	args: {
		flow: createFakeFlow({
			name: "flow",
		}),
	},
};
