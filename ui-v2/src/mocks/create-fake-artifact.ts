import {
	randAlphaNumeric,
	randNumber,
	randPastDate,
	randSentence,
	randUuid,
	randWord,
} from "@ngneat/falso";
import type { components } from "@/api/prefect";

type ArtifactType = components["schemas"]["Artifact"]["type"];

/**
 * Generates type-appropriate data for an artifact based on its type.
 * - markdown: Returns a markdown string with headers and formatting
 * - progress: Returns a number between 0 and 100
 * - table: Returns a JSON string of an array of objects
 * - image: Returns a placeholder image URL
 * - result/other: Returns the default object with random words
 */
const generateDataForType = (
	type: ArtifactType,
): string | number | { arr: string[] } => {
	switch (type) {
		case "markdown":
			return `# ${randWord()}\n\n${randSentence()}\n\n**${randWord()}**: ${randSentence()}`;
		case "progress":
			return randNumber({ min: 0, max: 100 });
		case "table":
			return JSON.stringify([
				{ key: randWord(), value: randWord() },
				{ key: randWord(), value: randWord() },
				{ key: randWord(), value: randWord() },
			]);
		case "image":
			return `https://picsum.photos/seed/${randAlphaNumeric({ length: 8 }).join("")}/400/300`;
		default:
			return { arr: randWord({ length: 5 }) };
	}
};

export const createFakeArtifact = (
	overrides?: Partial<components["schemas"]["Artifact"]>,
): components["schemas"]["Artifact"] => {
	const type = overrides?.type ?? "result";
	const data = overrides?.data ?? generateDataForType(type);

	return {
		id: randUuid(),
		created: randPastDate().toISOString(),
		updated: randPastDate().toISOString(),
		key: `key-${randAlphaNumeric({ length: 10 }).join()}`,
		type,
		description: randSentence(),
		data,
		metadata_: {
			key: randWord(),
			[randWord()]: randWord(),
		},
		flow_run_id: randUuid(),
		task_run_id: randUuid(),
		...overrides,
	};
};
