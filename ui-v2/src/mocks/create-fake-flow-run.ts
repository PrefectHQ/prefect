import { FlowRunWithDeploymentAndFlow } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";
import { createFakeDeployment } from "./create-fake-deployment";
import { createFakeFlow } from "./create-fake-flow";
import { createFakeState } from "./create-fake-state";

export const createFakeFlowRun = (
	overrides?: Partial<components["schemas"]["FlowRun"]>,
): components["schemas"]["FlowRun"] => {
	const { stateType, stateName } = createFakeState();

	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		name: `${faker.word.adjective()}-${faker.animal.type()}`,
		flow_id: faker.string.uuid(),
		state_id: faker.string.uuid(),
		deployment_id: null,
		deployment_version: null,
		work_queue_id: null,
		work_queue_name: null,
		flow_version: faker.string.hexadecimal(),
		parameters: {},
		idempotency_key: null,
		context: {},
		empirical_policy: {
			max_retries: 0,
			retry_delay_seconds: 0.0,
			retries: 0,
			retry_delay: 0,
			pause_keys: [],
			resuming: false,
			retry_type: null,
		},
		tags: [...faker.word.words({ count: { min: 0, max: 6 } })],
		labels: { "prefect.flow.id": faker.string.uuid() },
		parent_task_run_id: null,
		state_type: stateType,
		state_name: stateName,
		run_count: 1,
		expected_start_time: faker.date.past().toISOString(),
		next_scheduled_start_time: null,
		start_time: faker.date.past({ years: 0.1 }).toISOString(),
		end_time: faker.date.past({ years: 0.1 }).toISOString(),
		total_run_time: faker.number.int({ min: 1, max: 100 }),
		estimated_run_time: faker.number.float({ max: 30 }),
		estimated_start_time_delta: faker.number.float({ max: 30 }),
		auto_scheduled: false,
		infrastructure_document_id: null,
		infrastructure_pid: null,
		created_by: null,
		state: {
			id: faker.string.uuid(),
			type: stateType,
			name: stateName,
			timestamp: faker.date.past().toISOString(),
			message: "",
			data: null,
			state_details: {
				flow_run_id: faker.string.uuid(),
				task_run_id: faker.string.uuid(),
				child_flow_run_id: null,
				scheduled_time: null,
				cache_key: null,
				cache_expiration: null,
				deferred: false,
				untrackable_result: false,
				pause_timeout: null,
				pause_reschedule: false,
				pause_key: null,
				run_input_keyset: null,
				refresh_cache: null,
				retriable: null,
				transition_id: null,
				task_parameters_id: null,
			},
		},
		job_variables: {},
		...overrides,
	};
};

export const createFakeFlowRunWithDeploymentAndFlow =
	(): FlowRunWithDeploymentAndFlow => {
		const flowRun = createFakeFlowRun();

		return {
			...flowRun,
			deployment: createFakeDeployment(),
			flow: createFakeFlow(),
		};
	};
