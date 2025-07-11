import {
	randAlphaNumeric,
	randNumber,
	randPastDate,
	randUuid,
	randVerb,
	randWord,
} from "@ngneat/falso";
import type { TaskRun } from "@/api/task-runs";
import { createFakeState } from "./create-fake-state";

export const createFakeTaskRun = (overrides?: Partial<TaskRun>): TaskRun => {
	const state = overrides?.state ?? createFakeState();

	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: `${randVerb()}-task-${randAlphaNumeric({ length: 3 }).join()}`,
		flow_run_id: randUuid(),
		flow_run_name: `${randVerb()}-flow-${randAlphaNumeric({ length: 3 }).join()}`,
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
		state_type: state.type,
		state_name: state.name,
		run_count: randNumber({ max: 20 }),
		flow_run_run_count: randNumber({ max: 5 }),
		expected_start_time: randPastDate().toISOString(),
		next_scheduled_start_time: null,
		start_time: randPastDate().toISOString(),
		end_time: null,
		total_run_time: 0,
		estimated_run_time: randNumber({ max: 30, precision: 2 }),
		estimated_start_time_delta: randNumber({ max: 30, precision: 2 }),
		state,
		...overrides,
	};
};
