import type { components } from "@/api/prefect";

export type ApiRunStateFilter = {
	operator: "and_" | "or_";
	type?: { any_: components["schemas"]["StateType"][] };
	name?: { any_: string[] };
};

export const FLOW_RUN_STATES = [
	"Scheduled",
	"Late",
	"Resuming",
	"AwaitingRetry",
	"AwaitingConcurrencySlot",
	"Pending",
	"Paused",
	"Suspended",
	"Running",
	"Retrying",
	"Completed",
	"Cached",
	"Cancelled",
	"Cancelling",
	"Crashed",
	"Failed",
	"TimedOut",
] as const;
export type FlowRunState = (typeof FLOW_RUN_STATES)[number];
export const FLOW_RUN_STATES_NO_SCHEDULED = FLOW_RUN_STATES.filter(
	(flowStateFilter) => flowStateFilter !== "Scheduled",
);

/**
 * States to show when hiding scheduled runs.
 * Matches Vue's prefectStateNamesWithoutScheduled from prefect-ui-library.
 * Excludes all scheduled-type states (Scheduled, Late, Resuming, AwaitingRetry,
 * AwaitingConcurrencySlot) and Cached.
 */
export const FLOW_RUN_STATES_WITHOUT_SCHEDULED: FlowRunState[] = [
	"Pending",
	"Paused",
	"Suspended",
	"Running",
	"Retrying",
	"Completed",
	"Cancelled",
	"Cancelling",
	"Crashed",
	"Failed",
	"TimedOut",
];
export const FLOW_RUN_STATES_MAP = {
	Scheduled: "SCHEDULED",
	Late: "SCHEDULED",
	Resuming: "SCHEDULED",
	AwaitingRetry: "SCHEDULED",
	AwaitingConcurrencySlot: "SCHEDULED",
	Pending: "PENDING",
	Paused: "PAUSED",
	Suspended: "PAUSED",
	Running: "RUNNING",
	Retrying: "RUNNING",
	Completed: "COMPLETED",
	Cached: "COMPLETED",
	Cancelled: "CANCELLED",
	Cancelling: "CANCELLING",
	Crashed: "CRASHED",
	Failed: "FAILED",
	TimedOut: "FAILED",
} satisfies Record<FlowRunState, components["schemas"]["StateType"]>;

const STATE_TYPES_EXPAND_WHEN_PARTIAL = new Set<
	components["schemas"]["StateType"]
>(["FAILED", "COMPLETED"]);

function canonicalNamesForStateType(
	type: components["schemas"]["StateType"],
): FlowRunState[] {
	return FLOW_RUN_STATES.filter((s) => FLOW_RUN_STATES_MAP[s] === type);
}

/** Maps UI run-state checkboxes to API `flow_runs.state` / `task_runs.state` (type and/or name). */
export function buildApiStateFilterFromSelections(
	canonicalSelections: FlowRunState[],
	extraStateNames: string[],
): ApiRunStateFilter | undefined {
	const extras = extraStateNames
		.map((n) => n.trim())
		.filter((n) => n.length > 0);

	if (canonicalSelections.length === 0 && extras.length === 0) {
		return undefined;
	}

	const types = new Set<components["schemas"]["StateType"]>();
	const namesFromCanonical: string[] = [];

	const selectedByType = new Map<
		components["schemas"]["StateType"],
		FlowRunState[]
	>();
	for (const s of canonicalSelections) {
		const t = FLOW_RUN_STATES_MAP[s];
		const group = selectedByType.get(t);
		if (group) {
			group.push(s);
		} else {
			selectedByType.set(t, [s]);
		}
	}

	for (const [type, selected] of selectedByType) {
		const peers = canonicalNamesForStateType(type);
		const selectedSet = new Set(selected);
		const allPeersSelected = peers.every((p) => selectedSet.has(p));

		if (STATE_TYPES_EXPAND_WHEN_PARTIAL.has(type)) {
			types.add(type);
		} else if (allPeersSelected) {
			types.add(type);
		} else {
			namesFromCanonical.push(...selected);
		}
	}

	const nameList = [...new Set([...namesFromCanonical, ...extras])];

	if (types.size === 0 && nameList.length === 0) {
		return undefined;
	}

	let operator: "and_" | "or_" = "and_";
	const typeAny = types.size > 0 ? { any_: [...types].sort() } : undefined;
	const nameAny = nameList.length > 0 ? { any_: nameList } : undefined;

	if (typeAny && nameAny) {
		const onlyExtras = namesFromCanonical.length === 0 && extras.length > 0;
		operator = onlyExtras ? "and_" : "or_";
	}

	const result: ApiRunStateFilter = { operator };
	if (typeAny) {
		result.type = typeAny;
	}
	if (nameAny) {
		result.name = nameAny;
	}

	return result;
}
