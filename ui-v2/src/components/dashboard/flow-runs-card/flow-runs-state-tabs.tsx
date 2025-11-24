import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/utils";

type StateType = components["schemas"]["StateType"];
type TabState = StateType | "ALL";

const STATE_TYPES: readonly StateType[] = [
	"FAILED",
	"RUNNING",
	"COMPLETED",
	"SCHEDULED",
	"CANCELLED",
] as const;

const TAB_STATES: readonly TabState[] = ["ALL", ...STATE_TYPES] as const;

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
	states: StateType[];
	count: number;
	active: boolean;
};

const FlowRunStateCountPill = ({
	states,
	count,
	active,
}: FlowRunStateCountPillProps) => (
	<div className="flex flex-col items-center gap-1">
		<span className="h-1 w-4 rounded-full grid auto-cols-fr grid-flow-col overflow-hidden">
			{states.map((state) => (
				<span key={state} className={STATE_PILL_COLORS[state]} />
			))}
		</span>
		<span
			className={cn(
				"text-lg font-bold",
				active ? "text-foreground" : "text-muted-foreground",
			)}
		>
			{count}
		</span>
	</div>
);

type FlowRunStateTabsProps = {
	flowRuns: FlowRun[];
	selectedState: TabState;
	onStateChange: (state: TabState) => void;
};

export const FlowRunStateTabs = ({
	flowRuns,
	selectedState,
	onStateChange,
}: FlowRunStateTabsProps) => {
	const counts = useMemo(() => {
		const stateCounts: Record<StateType | "ALL", number> = {
			ALL: flowRuns.length,
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
		if (TAB_STATES.includes(value as TabState)) {
			onStateChange(value as TabState);
		}
	};

	return (
		<Tabs value={selectedState} onValueChange={handleValueChange}>
			<TabsList className="flex justify-between w-full">
				<TabsTrigger
					value="ALL"
					aria-label="All runs"
					className="bg-transparent shadow-none data-[state=active]:shadow-none border-none"
				>
					<FlowRunStateCountPill
						states={STATE_TYPES}
						count={counts.ALL}
						active={selectedState === "ALL"}
					/>
				</TabsTrigger>
				{STATE_TYPES.map((stateType) => (
					<TabsTrigger
						key={stateType}
						value={stateType}
						aria-label={`${stateType.toLowerCase()} runs`}
						className="bg-transparent shadow-none data-[state=active]:shadow-none border-none"
					>
						<FlowRunStateCountPill
							states={[stateType]}
							count={counts[stateType]}
							active={selectedState === stateType}
						/>
					</TabsTrigger>
				))}
			</TabsList>
		</Tabs>
	);
};
