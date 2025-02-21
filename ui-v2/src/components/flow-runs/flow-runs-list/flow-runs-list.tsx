import { Button } from "@/components/ui/button";
import { Typography } from "@/components/ui/typography";
import { FlowRunCard } from "./flow-run-card";
import type { FlowRunRow } from "./types";

type FlowRunCardProps =
	| {
			flowRuns: Array<FlowRunRow> | undefined;
			onClearFilters?: () => void;
	  }
	| {
			flowRuns: Array<FlowRunRow> | undefined;
			onSelect: (id: string, checked: boolean) => void;
			selectedRows: Set<string>;
			onClearFilters?: () => void;
	  };

export const FlowRunsList = ({
	flowRuns,
	onClearFilters,
	...props
}: FlowRunCardProps) => {
	if (!flowRuns) {
		// Todo: Add Skeleton Loading UX
		return "Loading...";
	}

	if (flowRuns.length === 0) {
		return (
			<div className="flex justify-center py-4">
				<div className="flex flex-col gap-2">
					<Typography>No runs found</Typography>
					{onClearFilters && (
						<Button onClick={onClearFilters}>Clear Filters</Button>
					)}
				</div>
			</div>
		);
	}

	return (
		<ul className="flex flex-col gap-2">
			{flowRuns.map((flowRun) => {
				// Variant for selectable list
				if ("onSelect" in props && "selectedRows" in props) {
					return (
						<li key={flowRun.id}>
							<FlowRunCard
								flowRun={flowRun}
								checked={props.selectedRows.has(flowRun.id)}
								onCheckedChange={(checked) =>
									props.onSelect(flowRun.id, checked)
								}
							/>
						</li>
					);
				}
				return (
					<li key={flowRun.id}>
						<FlowRunCard flowRun={flowRun} />
					</li>
				);
			})}
		</ul>
	);
};
