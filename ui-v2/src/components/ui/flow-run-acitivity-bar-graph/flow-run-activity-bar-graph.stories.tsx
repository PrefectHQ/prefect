import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import { FlowRunActivityBarChart } from ".";

import { faker } from "@faker-js/faker";

import type { components } from "@/api/prefect";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";

type StateType = components["schemas"]["StateType"];

const STATE_TYPE_VALUES = [
	"COMPLETED",
	"FAILED",
	"CRASHED",
	"CANCELLED",
	"RUNNING",
	"PENDING",
	"SCHEDULED",
	"PAUSED",
	"CANCELLING",
] as const satisfies readonly StateType[];

function createRandomEnrichedFlowRun(): React.ComponentProps<
	typeof FlowRunActivityBarChart
>["enrichedFlowRuns"][number] {
	const stateType = faker.helpers.arrayElement(STATE_TYPE_VALUES);
	const stateName =
		stateType.charAt(0).toUpperCase() + stateType.slice(1).toLowerCase();
	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		name: `${faker.word.adjective()}-${faker.animal.type()}`,
		flow_id: faker.string.uuid(),
		state_id: faker.string.uuid(),
		deployment_id: faker.string.uuid(),
		work_queue_id: faker.string.uuid(),
		work_queue_name: faker.string.uuid(),
		flow_version: faker.string.uuid(),
		deployment_version: faker.string.uuid(),
		idempotency_key: faker.string.uuid(),
		context: {},
		empirical_policy: {
			max_retries: faker.number.int(),
			retry_delay_seconds: faker.number.int(),
			retries: faker.number.int(),
			retry_delay: faker.number.int(),
			pause_keys: [],
			resuming: faker.datatype.boolean(),
		},
		tags: Array.from({ length: faker.number.int({ min: 0, max: 3 }) }, () =>
			faker.lorem.word(),
		),
		parent_task_run_id: faker.string.uuid(),
		state_type: stateType,
		state_name: stateName,
		run_count: faker.number.int(),
		start_time: faker.date.past({ years: 0.1 }).toISOString(),
		total_run_time: faker.number.int({ min: 1, max: 100 }),
		estimated_run_time: faker.number.int({ min: 1, max: 100 }),
		estimated_start_time_delta: faker.number.int(),
		auto_scheduled: faker.datatype.boolean(),
		infrastructure_document_id: faker.string.uuid(),
		infrastructure_pid: faker.string.uuid(),
		state: {
			id: faker.string.uuid(),
			type: stateType,
			name: stateName,
		},
		job_variables: {},
		deployment: {
			id: faker.string.uuid(),
			name: faker.airline.airplane().name,
			flow_id: faker.string.uuid(),
			paused: faker.datatype.boolean(),
			status: faker.helpers.arrayElement(["READY", "NOT_READY"]),
			enforce_parameter_schema: faker.datatype.boolean(),
			created: faker.date.past().toISOString(),
			updated: faker.date.past().toISOString(),
		},
		flow: {
			id: faker.string.uuid(),
			name: `${faker.finance.currencyName()} ${faker.commerce.product()}`,
			created: faker.date.past().toISOString(),
			updated: faker.date.past().toISOString(),
		},
	};
}

export default {
	title: "UI/FlowRunActivityBarChart",
	component: FlowRunActivityBarChart,
	parameters: {
		layout: "centered",
	},
	args: {
		enrichedFlowRuns: [],
		startDate: new Date(),
		endDate: new Date(),
		numberOfBars: 18,
	},
	render: function Render(
		args: ComponentProps<typeof FlowRunActivityBarChart>,
	) {
		args.endDate = new Date(args.endDate);
		args.startDate = new Date(args.startDate);
		const rootRoute = createRootRoute({
			component: () => <FlowRunActivityBarChart {...args} className="h-96" />,
		});
		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: {
				queryClient: new QueryClient(),
			},
		});
		// @ts-expect-error - Type error from using a test router
		return <RouterProvider router={router} />;
	},
} satisfies Meta<typeof FlowRunActivityBarChart>;

type Story = StoryObj<typeof FlowRunActivityBarChart>;

export const Randomized: Story = {
	args: {
		startDate: faker.date.past(),
		endDate: new Date(),
		enrichedFlowRuns: Array.from({ length: 18 }, createRandomEnrichedFlowRun),
	},
};
