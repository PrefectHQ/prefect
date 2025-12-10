import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type StateType = components["schemas"]["StateType"];

const STATE_TYPES: readonly StateType[][] = [
	["FAILED", "CRASHED"],
	["RUNNING", "PENDING", "CANCELLING"],
	["COMPLETED"],
	["SCHEDULED", "PAUSED"],
	["CANCELLED"],
] as const;

const STATE_PILL_COLORS: Record<StateType, string> = {
	COMPLETED: "bg-green-600",
	FAILED: "bg-red-600",
	RUNNING: "bg-blue-700",
	CANCELLED: "bg-gray-800",
	CRASHED: "bg-orange-600",
	PAUSED: "bg-gray-800",
	PENDING: "bg-gray-800",
	SCHEDULED: "bg-yellow-700",
	CANCELLING: "bg-gray-800",
};

type FlowRunStateCountPillProps = {
	states: readonly StateType[];
	count: number;
};

const FlowRunStateCountPill = ({
	states,
	count,
}: FlowRunStateCountPillProps) => (
	<>
		<span className="h-1 w-4 rounded-full grid auto-cols-fr grid-flow-col overflow-hidden">
			{states.map((state) => (
				<span key={state} className={STATE_PILL_COLORS[state]} />
			))}
		</span>

		{count}
	</>
);

type FlowRunStateTabsProps = {
	flowRuns: FlowRun[];
	selectedStates: StateType[];
	onStateChange: (states: StateType[]) => void;
	failedOrCrashedCount?: number;
};

export const FlowRunStateTabs = ({
	flowRuns,
	selectedStates,
	onStateChange,
}: FlowRunStateTabsProps) => {
	const counts = useMemo(() => {
		const stateCounts: Record<StateType, number> = {
			FAILED: 0,
			RUNNING: 0,
			COMPLETED: 0,
			SCHEDULED: 0,
			CANCELLED: 0,
			PENDING: 0,
			CRASHED: 0,
			PAUSED: 0,
			CANCELLING: 0,
		};

		for (const flowRun of flowRuns) {
			if (flowRun.state_type) {
				stateCounts[flowRun.state_type] =
					(stateCounts[flowRun.state_type] || 0) + 1;
			}
		}

		return stateCounts;
	}, [flowRuns]);

	const handleValueChange = (value: string) => {
		onStateChange(value.split("-").map((state) => state as StateType));
	};

	return (
		<div className="space-y-2">
			<Tabs value={selectedStates.join("-")} onValueChange={handleValueChange}>
				<TabsList className="flex justify-between w-full">
					{STATE_TYPES.map((stateType) => (
						<TabsTrigger
							key={stateType.join("-")}
							value={stateType.join("-")}
							aria-label={`${stateType.join("-").toLowerCase()} runs`}
							className="flex flex-col items-center gap-1"
						>
							<FlowRunStateCountPill
								states={stateType}
								count={stateType.reduce((acc, state) => acc + counts[state], 0)}
							/>
						</TabsTrigger>
					))}
				</TabsList>
			</Tabs>
		</div>
	);
};
