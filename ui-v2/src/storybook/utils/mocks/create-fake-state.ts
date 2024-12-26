import type { components } from "@/api/prefect";
import { faker } from "@faker-js/faker";

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
	const stateType = faker.helpers.arrayElement(STATE_TYPE_VALUES);
	const stateName =
		stateType.charAt(0).toUpperCase() + stateType.slice(1).toLowerCase();

	return { stateType, stateName };
};
