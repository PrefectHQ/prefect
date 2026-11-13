import { RUN_STATES, type StateType } from "@/api/flow-runs/constants";

export const STATE_TYPES = Object.keys(RUN_STATES) as StateType[];
export const NON_SCHEDULED_STATE_TYPES = STATE_TYPES.filter(
	(type) => type !== "SCHEDULED",
);

// Accept existing comma-separated URLs; arrays preserve commas in custom names.
export function parseStateNames(
	value: string | string[] | undefined,
): string[] {
	return Array.isArray(value)
		? value
		: (value?.split(",").filter(Boolean) ?? []);
}

export function serializeStateNames(names: string[]): string | string[] {
	return names.some((name) => name.includes(",")) ? names : names.join(",");
}

export function buildStateFilter(names: string[], types: StateType[] = []) {
	if (!names.length && !types.length) return undefined;
	return {
		operator: "and_" as const,
		...(names.length > 0 && { name: { any_: names } }),
		...(types.length > 0 && { type: { any_: types } }),
	};
}
