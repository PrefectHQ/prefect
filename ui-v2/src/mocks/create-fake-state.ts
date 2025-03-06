import type { components } from "@/api/prefect";
import { capitalize } from "@/utils";
import { rand } from "@ngneat/falso";

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

export const createFakeState = () => {
	const stateType = rand(STATE_TYPE_VALUES);
	const stateName = capitalize(stateType);

	return { stateType, stateName };
};
