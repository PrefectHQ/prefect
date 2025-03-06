import type { components } from "@/api/prefect";
import {
	randAlphaNumeric,
	randNumber,
	randPastDate,
	randUuid,
	randVerb,
	randWord,
} from "@ngneat/falso";
import { createFakeState } from "./create-fake-state";

export const createFakeTaskRun = (
	overrides?: Partial<components["schemas"]["TaskRun"]>,
): components["schemas"]["TaskRun"] => {
	const { stateType, stateName } = createFakeState();

	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: `${randVerb()}-task-${randAlphaNumeric({ length: 3 }).join()}`,
		flow_run_id: randUuid(),
		task_key: "say_hello-6b199e75",
		dynamic_key: randUuid(),
		cache_key: null,
		cache_expiration: null,
		task_version: null,
		empirical_policy: {
			max_retries: 0,
			retry_delay_seconds: 0,
			retries: 0,
			retry_delay: 0,
			retry_jitter_factor: null,
		},
		tags: randWord({ length: randNumber({ min: 0, max: 6 }) }),
		labels: {},
		state_id: randUuid(),
		task_inputs: {
			name: [],
		},
		state_type: stateType,
		state_name: stateName,
		run_count: randNumber({ max: 20 }),
		flow_run_run_count: randNumber({ max: 5 }),
		expected_start_time: randPastDate().toISOString(),
		next_scheduled_start_time: null,
		start_time: randPastDate().toISOString(),
		end_time: null,
		total_run_time: 0,
		estimated_run_time: randNumber({ max: 30, precision: 2 }),
		estimated_start_time_delta: randNumber({ max: 30, precision: 2 }),
		state: {
			id: randUuid(),
			type: stateType,
			name: stateName,
			timestamp: randPastDate().toISOString(),
			message: "",
			data: null,
			state_details: {
				flow_run_id: randUuid(),
				task_run_id: randUuid(),
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
		...overrides,
	};
};
