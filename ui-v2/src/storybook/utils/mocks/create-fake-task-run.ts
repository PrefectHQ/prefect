import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";
import { createFakeState } from "./create-fake-state";

export const createFakeTaskRun = (
	overrides?: Partial<components["schemas"]["TaskRun"]>,
): components["schemas"]["TaskRun"] => {
	const { stateType, stateName } = createFakeState();

	return {
		id: faker.string.uuid(),
		created: faker.date.past().toISOString(),
		updated: faker.date.past().toISOString(),
		name: `${faker.word.verb()}-task-${faker.string.alphanumeric({ length: 3 })}`,
		flow_run_id: faker.string.uuid(),
		task_key: "say_hello-6b199e75",
		dynamic_key: faker.string.uuid(),
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
		tags: [...faker.word.words({ count: { min: 0, max: 6 } })],
		labels: {},
		state_id: faker.string.uuid(),
		task_inputs: {
			name: [],
		},
		state_type: stateType,
		state_name: stateName,
		run_count: faker.number.int({ max: 20 }),
		flow_run_run_count: faker.number.int({ max: 5 }),
		expected_start_time: faker.date.past().toISOString(),
		next_scheduled_start_time: null,
		start_time: faker.date.past().toISOString(),
		end_time: null,
		total_run_time: 0,
		estimated_run_time: faker.number.float({ max: 30 }),
		estimated_start_time_delta: faker.number.float({ max: 30 }),
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
		...overrides,
	};
};
