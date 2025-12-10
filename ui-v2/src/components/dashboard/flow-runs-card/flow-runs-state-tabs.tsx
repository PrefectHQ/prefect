import type { components } from "@/api/prefect";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type StateType = components["schemas"]["StateType"];

export type StateTypeCounts = Record<StateType, number>;

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
	stateCounts: StateTypeCounts;
	selectedStates: StateType[];
	onStateChange: (states: StateType[]) => void;
};

export const FlowRunStateTabs = ({
	stateCounts,
	selectedStates,
	onStateChange,
}: FlowRunStateTabsProps) => {
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
								count={stateType.reduce(
									(acc, state) => acc + stateCounts[state],
									0,
								)}
							/>
						</TabsTrigger>
					))}
				</TabsList>
			</Tabs>
		</div>
	);
};
