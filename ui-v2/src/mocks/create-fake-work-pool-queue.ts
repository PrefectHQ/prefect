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

	// Always create a default queue first (not deletable)
	queues.push(
		createFakeWorkPoolQueue({
			name: "default",
			work_pool_name: workPoolName,
			priority: 1,
			is_paused: false,
			status: "READY",
		}),
	);

	// Create additional queues (all deletable)
	for (let i = 1; i < count; i++) {
		const queueOverrides = overrides?.[i] || {};
		queues.push(
			createFakeWorkPoolQueue({
				work_pool_name: workPoolName,
				name: `queue-${i}`,
				...queueOverrides,
			}),
		);
	}

	return queues;
};

export const createFakeWorkPoolQueuesWithPermissions = (
	workPoolName: string,
	count = 5,
): WorkPoolQueue[] => {
	const queues = createFakeWorkPoolQueues(workPoolName, count);

	// Add some variety to the queues for testing
	if (queues.length > 1) {
		// Make second queue paused
		queues[1] = { ...queues[1], is_paused: true, status: "PAUSED" };
	}
	if (queues.length > 2) {
		// Make third queue have high concurrency
		queues[2] = { ...queues[2], concurrency_limit: 50 };
	}
	if (queues.length > 3) {
		// Make fourth queue have high priority
		queues[3] = { ...queues[3], priority: 10 };
	}

	return queues;
};

// Mock count for late flow runs - this would be returned by the count endpoint
export const mockLateFlowRunsCount = 3;
