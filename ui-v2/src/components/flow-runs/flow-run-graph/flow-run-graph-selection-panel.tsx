import { type GraphItemSelection, isNodeSelection } from "@prefecthq/graphs";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildGetFlowRunDetailsQuery } from "@/api/flow-runs";
import { buildGetTaskRunQuery } from "@/api/task-runs";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { Icon } from "@/components/ui/icons";
import { KeyValue } from "@/components/ui/key-value";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { secondsToApproximateString } from "@/utils/seconds";

type FlowRunGraphSelectionPanelProps = {
	selection: GraphItemSelection;
	onClose: () => void;
};

export function FlowRunGraphSelectionPanel({
	selection,
	onClose,
}: FlowRunGraphSelectionPanelProps) {
	if (!isNodeSelection(selection)) {
		return null;
	}

	return (
		<div className="absolute top-4 right-4 z-10 w-72 rounded-lg border bg-card p-4 shadow-md">
			<Suspense fallback={<SelectionPanelSkeleton onClose={onClose} />}>
				{selection.kind === "task-run" && (
					<TaskRunDetails taskRunId={selection.id} onClose={onClose} />
				)}
				{selection.kind === "flow-run" && (
					<FlowRunDetails flowRunId={selection.id} onClose={onClose} />
				)}
			</Suspense>
		</div>
	);
}

type SelectionPanelSkeletonProps = {
	onClose: () => void;
};

function SelectionPanelSkeleton({ onClose }: SelectionPanelSkeletonProps) {
	return (
		<div className="space-y-3">
			<div className="flex items-start justify-between gap-2">
				<Skeleton className="h-6 w-3/4" />
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close panel"
					className="shrink-0 -mt-1 -mr-2"
				>
					<Icon id="X" className="size-4" />
				</Button>
			</div>
			<Skeleton className="h-5 w-1/2" />
			<Skeleton className="h-5 w-full" />
			<Skeleton className="h-5 w-2/3" />
			<Skeleton className="h-5 w-1/2" />
		</div>
	);
}

type TaskRunDetailsProps = {
	taskRunId: string;
	onClose: () => void;
};

function TaskRunDetails({ taskRunId, onClose }: TaskRunDetailsProps) {
	const { data: taskRun } = useSuspenseQuery(buildGetTaskRunQuery(taskRunId));

	const duration =
		taskRun.estimated_run_time && taskRun.estimated_run_time > 0
			? taskRun.estimated_run_time
			: (taskRun.total_run_time ?? 0);

	return (
		<div className="space-y-3">
			<div className="flex items-start justify-between gap-2">
				<h3 className="font-semibold text-base">
					<Link
						to="/runs/task-run/$id"
						params={{ id: taskRunId }}
						className="hover:underline text-foreground"
					>
						{taskRun.name}
					</Link>
				</h3>
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close panel"
					className="shrink-0 -mt-1 -mr-2"
				>
					<Icon id="X" className="size-4" />
				</Button>
			</div>
			<div className="space-y-3">
				{taskRun.state && (
					<KeyValue
						label="State"
						value={
							<StateBadge type={taskRun.state.type} name={taskRun.state.name} />
						}
					/>
				)}
				<KeyValue label="Task Run ID" value={taskRun.id} copyable />
				<KeyValue
					label="Duration"
					value={duration > 0 ? secondsToApproximateString(duration) : "-"}
				/>
				<KeyValue
					label="Created"
					value={<FormattedDate date={taskRun.created} />}
				/>
				{taskRun.tags && taskRun.tags.length > 0 && (
					<KeyValue
						label="Tags"
						value={<TagBadgeGroup tags={taskRun.tags} />}
					/>
				)}
			</div>
		</div>
	);
}

type FlowRunDetailsProps = {
	flowRunId: string;
	onClose: () => void;
};

function FlowRunDetails({ flowRunId, onClose }: FlowRunDetailsProps) {
	const { data: flowRun } = useSuspenseQuery(
		buildGetFlowRunDetailsQuery(flowRunId),
	);

	const duration = flowRun.total_run_time ?? 0;

	return (
		<div className="space-y-3">
			<div className="flex items-start justify-between gap-2">
				<h3 className="font-semibold text-base">
					<Link
						to="/runs/flow-run/$id"
						params={{ id: flowRunId }}
						className="hover:underline text-foreground"
					>
						{flowRun.name}
					</Link>
				</h3>
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close panel"
					className="shrink-0 -mt-1 -mr-2"
				>
					<Icon id="X" className="size-4" />
				</Button>
			</div>
			<div className="space-y-3">
				{flowRun.state && (
					<KeyValue
						label="State"
						value={
							<StateBadge type={flowRun.state.type} name={flowRun.state.name} />
						}
					/>
				)}
				<KeyValue label="Flow Run ID" value={flowRun.id} copyable />
				<KeyValue
					label="Duration"
					value={duration > 0 ? secondsToApproximateString(duration) : "-"}
				/>
				<KeyValue
					label="Created"
					value={<FormattedDate date={flowRun.created} />}
				/>
				{flowRun.tags && flowRun.tags.length > 0 && (
					<KeyValue
						label="Tags"
						value={<TagBadgeGroup tags={flowRun.tags} />}
					/>
				)}
			</div>
		</div>
	);
}
