import {
	randAlphaNumeric,
	randPastDate,
	randSentence,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

export const createFakeArtifact = (
	overrides?: Partial<components["schemas"]["Artifact"]>,
): components["schemas"]["Artifact"] => {
	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		key: `key-${randAlphaNumeric({ length: 10 }).join()}`,
		type: "result",
		description: randSentence(),
		data: {
			arr: randWord({ length: 5 }),
		},
		metadata_: {
			key: randWord(),
			[randWord()]: randWord(),
		},
		flow_run_id: randUuid(),
		task_run_id: randUuid(),
		...overrides,
	};
};
