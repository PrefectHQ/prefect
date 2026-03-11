import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { FormattedDate } from "@/components/ui/formatted-date";

type FlowRunsAccordionHeaderProps = {
	/** The flow to display */
	flow: Flow;
	/** Count of flow runs for this flow */
	count: number;
	/** Most recent flow run for this flow (if any) */
	lastFlowRun?: FlowRun;
};

/**
 * Header component for each accordion section.
 * Displays flow name, last run time, and count of runs.
 */
export function FlowRunsAccordionHeader({
	flow,
	count,
	lastFlowRun,
}: FlowRunsAccordionHeaderProps) {
	return (
		<div className="flex w-full items-center justify-between gap-4 pr-2">
			<div className="flex flex-col items-start gap-1">
				<FlowIconText
					flow={flow}
					className="text-sm font-medium text-foreground hover:underline flex items-center gap-1"
					onClick={(e) => e.stopPropagation()}
				/>
				{lastFlowRun?.start_time && (
					<FormattedDate
						date={new Date(lastFlowRun.start_time)}
						format="relative"
						className="text-xs text-muted-foreground"
					/>
				)}
			</div>
			<span className="text-sm font-medium text-muted-foreground">
				{count ?? 0}
			</span>
		</div>
	);
}
