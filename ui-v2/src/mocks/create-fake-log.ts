import {
	randNumber,
	randPastDate,
	randSentence,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeLog = (
	overrides?: Partial<components["schemas"]["Log"]>,
): components["schemas"]["Log"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		level: randNumber({ min: 0, max: 50 }),
		name: `${randWord()}.${randWord()}`,
		message: randSentence(),
		timestamp: randPastDate({ years: 0.01 }).toISOString(),
		flow_run_id: randUuid(),
		task_run_id: randUuid(),
		...overrides,
	};
};
