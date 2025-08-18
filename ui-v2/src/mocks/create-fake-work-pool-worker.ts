import {
	rand,
	randAlphaNumeric,
	randPastDate,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { WorkPoolWorker } from "@/api/work-pools";

export const createFakeWorkPoolWorker = (
	overrides?: Partial<WorkPoolWorker>,
): WorkPoolWorker => ({
	id: randUuid(),
	created: randPastDate().toISOString(),
	updated: randPastDate().toISOString(),
	name: `${randWord()}-${randAlphaNumeric({ length: 6 }).join("").toLowerCase()}`,
	work_pool_id: randUuid(),
	last_heartbeat_time: randPastDate().toISOString(),
	status: rand(["ONLINE", "OFFLINE"]),
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
