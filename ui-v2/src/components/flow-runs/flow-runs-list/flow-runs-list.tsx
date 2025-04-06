import {
	FlowRunCard,
	type FlowRunCardData,
} from "@/components/flow-runs/flow-run-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";

type FlowRunCardProps =
	| {
			flowRuns: Array<FlowRunCardData> | undefined;
			onClearFilters?: () => void;
	  }
	| {
			flowRuns: Array<FlowRunCardData> | undefined;
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
		return <LoadingSkeleton numSkeletons={5} />;
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

type LoadingSkeletonProps = {
	numSkeletons?: number;
};
const LoadingSkeleton = ({ numSkeletons = 1 }: LoadingSkeletonProps) => (
	<ul className="flex flex-col gap-1">
		{Array.from({ length: numSkeletons }).map((_, i) => (
			// biome-ignore lint/suspicious/noArrayIndexKey: okay for static skeleton list
			<li key={i}>
				<Card className="flex flex-col gap-2 p-4">
					<div className="flex justify-between">
						<Skeleton className="h-4 w-[350px]" />
						<Skeleton className="h-4 w-[400px]" />
					</div>
					<Skeleton className="h-4 w-[400px]" />
					<Skeleton className="h-4 w-[200px]" />
				</Card>
			</li>
		))}
	</ul>
);
