import {
	randAnimal,
	randHex,
	randNumber,
	randPastDate,
	randProductAdjective,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type {
	FlowRun,
	FlowRunWithDeploymentAndFlow,
	FlowRunWithFlow,
} from "@/api/flow-runs";
import { createFakeDeployment } from "./create-fake-deployment";
import { createFakeFlow } from "./create-fake-flow";
import { createFakeState } from "./create-fake-state";

export const createFakeFlowRun = (overrides?: Partial<FlowRun>): FlowRun => {
	const state = createFakeState();

	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: `${randProductAdjective()}-${randAnimal()}`,
		flow_id: randUuid(),
		state_id: randUuid(),
		deployment_id: null,
		deployment_version: null,
		work_queue_id: null,
		work_queue_name: null,
		flow_version: randHex(),
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
		tags: randWord({ length: randNumber({ min: 0, max: 6 }) }),
		labels: { "prefect.flow.id": randUuid() },
		parent_task_run_id: null,
		state_type: state.type,
		state_name: state.name,
		run_count: 1,
		expected_start_time: randPastDate().toISOString(),
		next_scheduled_start_time: null,
		start_time: randPastDate({ years: 0.1 }).toISOString(),
		end_time: randPastDate({ years: 0.1 }).toISOString(),
		total_run_time: randNumber({ min: 1, max: 100 }),
		estimated_run_time: randNumber({ max: 30 }),
		estimated_start_time_delta: randNumber({ max: 30, precision: 2 }),
		auto_scheduled: false,
		infrastructure_document_id: null,
		infrastructure_pid: null,
		created_by: null,
		state,
		job_variables: {},
		...overrides,
	};
};

export const createFakeFlowRunWithFlow = (
	overrides?: Partial<FlowRun>,
): FlowRunWithFlow => {
	const flowRun = createFakeFlowRun();
	return {
		...flowRun,
		flow: createFakeFlow(),
		...overrides,
	};
};

export const createFakeFlowRuns = (numberOfFlowRuns = 10): FlowRun[] => {
	return Array.from({ length: numberOfFlowRuns }, () => createFakeFlowRun());
};

export const createFakeFlowRunWithDeploymentAndFlow = (
	overrides?: Partial<FlowRun>,
): FlowRunWithDeploymentAndFlow => {
	const flowRun = createFakeFlowRun();
	return {
		...flowRun,
		deployment: createFakeDeployment(),
		flow: createFakeFlow(),
		...overrides,
	};
};
