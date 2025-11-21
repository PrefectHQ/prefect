import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { buildFilterFlowRunsQuery, type FlowRunsFilter } from "@/api/flow-runs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type FlowRunsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
		tags?: string[];
		hideSubflows?: boolean;
	};
};

export function FlowRunsCard({ filter }: FlowRunsCardProps) {
	const flowRunsFilter: FlowRunsFilter = useMemo(() => {
		const baseFilter: FlowRunsFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
		};

		const flowRunsFilterObj: NonNullable<FlowRunsFilter["flow_runs"]> = {
			operator: "and_",
		};

		if (filter?.startDate && filter?.endDate) {
			flowRunsFilterObj.start_time = {
				after_: filter.startDate,
				before_: filter.endDate,
			};
		}

		if (filter?.tags && filter.tags.length > 0) {
			flowRunsFilterObj.tags = {
				operator: "and_",
				all_: filter.tags,
			};
		}

		if (filter?.hideSubflows) {
			flowRunsFilterObj.parent_task_run_id = {
				operator: "and_",
				is_null_: true,
			};
		}

		if (Object.keys(flowRunsFilterObj).length > 1) {
			baseFilter.flow_runs = flowRunsFilterObj;
		}

		return baseFilter;
	}, [filter?.startDate, filter?.endDate, filter?.tags, filter?.hideSubflows]);

	const { data: flowRuns } = useSuspenseQuery(
		buildFilterFlowRunsQuery(flowRunsFilter, 30000),
	);

	return (
		<Card>
			<CardHeader>
				<CardTitle>Flow Runs</CardTitle>
				{flowRuns.length > 0 && (
					<span className="text-sm text-muted-foreground">
						{flowRuns.length} total
					</span>
				)}
			</CardHeader>
			<CardContent>
				{flowRuns.length === 0 ? (
					<div className="my-8 text-center text-sm text-muted-foreground">
						<p>No flow runs found</p>
					</div>
				) : (
					<div className="h-64 bg-muted rounded-md flex items-center justify-center">
						<span className="text-muted-foreground">
							Flow runs chart and table will appear here
						</span>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
