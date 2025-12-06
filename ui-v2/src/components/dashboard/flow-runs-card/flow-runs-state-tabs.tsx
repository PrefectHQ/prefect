import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/utils";

type StateType = components["schemas"]["StateType"];

const STATE_TYPES: readonly StateType[] = [
	"FAILED",
	"RUNNING",
	"COMPLETED",
	"SCHEDULED",
	"CANCELLED",
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
	selectedState: StateType;
	onStateChange: (state: StateType) => void;
	failedOrCrashedCount?: number;
};

export const FlowRunStateTabs = ({
	flowRuns,
	selectedState,
	onStateChange,
	failedOrCrashedCount,
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
		if (STATE_TYPES.includes(value as StateType)) {
			onStateChange(value as StateType);
		}
	};

	// Generate state-aware summary message
	const getSummaryMessage = (): string | null => {
		if (selectedState === "FAILED" && failedOrCrashedCount === 0) {
			return "You currently have 0 failed or crashed runs.";
		}
		return null;
	};

	const summaryMessage = getSummaryMessage();

	return (
		<div className="space-y-2">
			<Tabs value={selectedState} onValueChange={handleValueChange}>
				<TabsList className="flex justify-between w-full">
					{STATE_TYPES.map((stateType) => (
						<TabsTrigger
							key={stateType}
							value={stateType}
							aria-label={`${stateType.toLowerCase()} runs`}
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
			{summaryMessage && (
				<p className="text-sm text-muted-foreground">{summaryMessage}</p>
			)}
		</div>
	);
};
