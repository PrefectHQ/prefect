import { useMemo } from "react";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { StateBadge } from "@/components/ui/state-badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
			<TabsList>
				<TabsTrigger value="ALL">
					<span className="font-medium">All</span>
					<span className="ml-1.5 text-muted-foreground">{counts.ALL}</span>
				</TabsTrigger>
				{STATE_TYPES.map((stateType) => (
					<TabsTrigger key={stateType} value={stateType}>
						<StateBadge type={stateType} className="text-xs" />
						<span className="ml-1.5 text-muted-foreground">
							{counts[stateType]}
						</span>
					</TabsTrigger>
				))}
			</TabsList>
		</Tabs>
	);
};
