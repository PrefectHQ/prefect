import type { WorkPoolWorker } from "@/api/work-pools";

export const createFakeWorkPoolWorker = (
	overrides?: Partial<WorkPoolWorker>,
): WorkPoolWorker => ({
	id: `worker-${Math.random().toString(36).substr(2, 9)}`,
	created: new Date(
		Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000,
	).toISOString(),
	updated: new Date(
		Date.now() - Math.random() * 24 * 60 * 60 * 1000,
	).toISOString(),
	name: `worker-${Math.random().toString(36).substr(2, 6)}`,
	work_pool_id: `pool-${Math.random().toString(36).substr(2, 9)}`,
	last_heartbeat_time: new Date(
		Date.now() - Math.random() * 24 * 60 * 60 * 1000,
	).toISOString(),
	status: Math.random() > 0.5 ? "ONLINE" : "OFFLINE",
	...overrides,
});

export const createFakeWorkPoolWorkers = (
	count = 3,
	overrides?: Partial<WorkPoolWorker>,
): WorkPoolWorker[] => {
	return Array.from({ length: count }, () =>
		createFakeWorkPoolWorker(overrides),
	);
};
