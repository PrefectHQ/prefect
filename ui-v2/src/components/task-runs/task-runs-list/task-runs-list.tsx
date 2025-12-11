import type { TaskRun } from "@/api/task-runs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";
import { TaskRunsListItemWithData } from "./task-runs-list-item";

type TaskRunsListProps =
	| {
			taskRuns: Array<TaskRun> | undefined;
			onClearFilters?: () => void;
	  }
	| {
			taskRuns: Array<TaskRun> | undefined;
			onSelect: (id: string, checked: boolean) => void;
			selectedRows: Set<string>;
			onClearFilters?: () => void;
	  };

export const TaskRunsList = ({
	taskRuns,
	onClearFilters,
	...props
}: TaskRunsListProps) => {
	if (!taskRuns) {
		return <LoadingSkeleton numSkeletons={5} />;
	}

	if (taskRuns.length === 0) {
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
			{taskRuns.map((taskRun) => {
				if ("onSelect" in props && "selectedRows" in props) {
					return (
						<li key={taskRun.id}>
							<TaskRunsListItemWithData
								taskRun={taskRun}
								checked={props.selectedRows.has(taskRun.id)}
								onCheckedChange={(checked) =>
									props.onSelect(taskRun.id, checked)
								}
							/>
						</li>
					);
				}
				return (
					<li key={taskRun.id}>
						<TaskRunsListItemWithData taskRun={taskRun} />
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
