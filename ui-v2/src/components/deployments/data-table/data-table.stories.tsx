import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { type ComponentProps, useMemo, useState } from "react";
import { fn } from "storybook/test";
import type { FlowRunWithDeploymentAndFlow } from "@/api/flow-runs";
import { createFakeDeploymentWithFlow } from "@/mocks";
import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { DeploymentsDataTable } from ".";

export default {
	title: "Components/Deployments/DataTable",
	component: DeploymentsDataTable,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof DeploymentsDataTable>;

const flowRunCache = new Map<string, FlowRunWithDeploymentAndFlow[]>();

type StoryArgs = Omit<
	ComponentProps<typeof DeploymentsDataTable>,
	"deployments" | "pageCount" | "pagination"
> & { numberOfDeployments: number };

export const Default: StoryObj<StoryArgs> = {
	name: "Randomized Data",
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/filter"), async ({ request }) => {
					const { limit, deployments } = (await request.json()) as {
						limit: number;
						deployments: object;
					};

					if (!flowRunCache.has(JSON.stringify({ limit, deployments }))) {
						const flowRuns = Array.from(
							{ length: limit },
							createFakeFlowRunWithDeploymentAndFlow,
						);
						flowRunCache.set(JSON.stringify({ limit, deployments }), flowRuns);
						return HttpResponse.json(flowRuns);
					}

					return HttpResponse.json(
						flowRunCache.get(JSON.stringify({ limit, deployments })),
					);
				}),
			],
		},
	},
	args: {
		numberOfDeployments: 10,
		onPaginationChange: fn(),
	},
	render: (
		args: Omit<
			ComponentProps<typeof DeploymentsDataTable>,
			"deployments" | "pageCount" | "pagination"
		> & { numberOfDeployments: number },
	) => {
		const { numberOfDeployments, ...rest } = args;
		const [pageIndex, setPageIndex] = useState(0); // eslint-disable-line react-hooks/rules-of-hooks
		const [pageSize, setPageSize] = useState(10); // eslint-disable-line react-hooks/rules-of-hooks

		// eslint-disable-next-line react-hooks/rules-of-hooks
		const deployments = useMemo(() => {
			return Array.from(
				{ length: numberOfDeployments },
				createFakeDeploymentWithFlow,
			);
		}, [numberOfDeployments]);

		return (
			<DeploymentsDataTable
				{...rest}
				deployments={deployments.slice(
					pageIndex * pageSize,
					(pageIndex + 1) * pageSize,
				)}
				pagination={{
					pageIndex,
					pageSize,
				}}
				columnFilters={[]}
				pageCount={Math.ceil(numberOfDeployments / pageSize)}
				onPaginationChange={(pagination) => {
					setPageIndex(pagination.pageIndex);
					setPageSize(pagination.pageSize);
					rest.onPaginationChange(pagination);
				}}
			/>
		);
	},
};

export const Empty: StoryObj = {
	name: "Empty",
	args: {
		deployments: [],
	},
};
