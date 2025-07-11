import { rand, randPastDate, randUuid } from "@ngneat/falso";
import type { components } from "@/api/prefect";
import { capitalize } from "@/utils";

type StateType = components["schemas"]["StateType"];

const STATE_TYPE_VALUES = [
	"COMPLETED",
	"FAILED",
	"CRASHED",
	"CANCELLED",
	"RUNNING",
	"PENDING",
	"SCHEDULED",
	"PAUSED",
	"CANCELLING",
] as const satisfies readonly StateType[];

export const createFakeState = (
	overrides?: Partial<components["schemas"]["State"]>,
): components["schemas"]["State"] => {
	const stateType = rand(STATE_TYPE_VALUES);
	const stateName = capitalize(stateType);

	return {
		id: randUuid(),
		type: stateType,
		name: stateName,
		timestamp: randPastDate().toISOString(),
		message: "",
		data: null,
		...overrides,
	};
};
