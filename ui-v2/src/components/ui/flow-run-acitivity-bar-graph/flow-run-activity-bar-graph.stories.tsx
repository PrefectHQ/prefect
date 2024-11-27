import { FlowRunActivityBarChart } from ".";
import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";

import { faker } from "@faker-js/faker";
import { startCase, lowerCase } from "lodash-es";

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
] as const;

function createRandomEnrichedFlowRun(): React.ComponentProps<
	typeof FlowRunActivityBarChart
>["enrichedFlowRuns"][number] {
	const stateType = faker.helpers.arrayElement(STATE_TYPE_VALUES);
	const stateName = startCase(lowerCase(stateType));
	return {
		id: faker.string.uuid(),
		created: faker.date.past({ years: 0.1 }).toISOString(),
		updated: faker.date.past({ years: 0.1 }).toISOString(),
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
		tags: [],
		parent_task_run_id: faker.string.uuid(),
		state_type: stateType,
		state_name: stateName,
		run_count: faker.number.int(),
		start_time: faker.date.past({ years: 0.1 }).toISOString(),
		total_run_time: faker.number.int(),
		estimated_run_time: faker.number.int(),
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
		},
		flow: {
			id: faker.string.uuid(),
			name: faker.string.uuid(),
		},
	};
}

export default {
	title: "UI/FlowRunActivityBarChart",
	component: FlowRunActivityBarChart,
	args: {
		enrichedFlowRuns: [],
		startDate: new Date(),
		endDate: new Date(),
	},
	render: function Render(
		args: ComponentProps<typeof FlowRunActivityBarChart>,
	) {
		args.endDate = new Date(args.endDate);
		args.startDate = new Date(args.startDate);
		return <FlowRunActivityBarChart {...args} className="h-96" />;
	},
} satisfies Meta<typeof FlowRunActivityBarChart>;

type Story = StoryObj<typeof FlowRunActivityBarChart>;

export const Randomized: Story = {
	args: {
		startDate: faker.date.past({ years: 0.15 }),
		endDate: new Date(),
		enrichedFlowRuns: Array.from({ length: 18 }, createRandomEnrichedFlowRun),
	},
};
