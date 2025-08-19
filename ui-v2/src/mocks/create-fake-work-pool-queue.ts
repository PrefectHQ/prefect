import {
	randNumber,
	randPastDate,
	randProductAdjective,
	randProductName,
	randUuid,
} from "@ngneat/falso";
import type {
	WorkPoolQueue,
	WorkPoolQueueStatus,
} from "@/api/work-pool-queues";

export const createFakeWorkPoolQueue = (
	overrides?: Partial<WorkPoolQueue>,
): WorkPoolQueue => {
	const statuses: WorkPoolQueueStatus[] = ["READY", "PAUSED", "NOT_READY"];
	const isDefault = overrides?.name === "default";

	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		name: isDefault ? "default" : `${randProductAdjective()} queue`,
		description: isDefault
			? "Default queue for the work pool"
			: `${randProductAdjective()} ${randProductName()}`,
		is_paused: isDefault ? false : Math.random() < 0.2, // Default queue is never paused, others 20% chance of being paused
		concurrency_limit:
			Math.random() < 0.5 ? null : randNumber({ min: 1, max: 100 }),
		priority: isDefault ? 1 : randNumber({ min: 1, max: 10 }),
		work_pool_id: randUuid(),
		work_pool_name: `${randProductAdjective()} work pool`,
		last_polled: randPastDate().toISOString(),
		status: isDefault
			? "READY"
			: statuses[Math.floor(Math.random() * statuses.length)],
		...overrides,
	};
};

export const createFakeWorkPoolQueues = (
	workPoolName: string,
	count = 5,
	overrides?: Partial<WorkPoolQueue>[],
): WorkPoolQueue[] => {
	const queues: WorkPoolQueue[] = [];

	// Always create a default queue first
	queues.push(
		createFakeWorkPoolQueue({
			name: "default",
			work_pool_name: workPoolName,
			priority: 1,
			is_paused: false,
			status: "READY",
		}),
	);

	// Create additional queues
	for (let i = 1; i < count; i++) {
		const queueOverrides = overrides?.[i] || {};
		queues.push(
			createFakeWorkPoolQueue({
				work_pool_name: workPoolName,
				...queueOverrides,
			}),
		);
	}

	return queues;
};
