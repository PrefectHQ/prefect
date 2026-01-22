import {
	type GraphItemSelection,
	isNodeSelection,
	type NodeSelection,
} from "@prefecthq/graphs";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import { Suspense } from "react";
import { buildGetFlowRunDetailsQuery, type FlowRun } from "@/api/flow-runs";
import { buildGetTaskRunQuery, type TaskRun } from "@/api/task-runs";
import { Button } from "@/components/ui/button";
import { FormattedDate } from "@/components/ui/formatted-date/formatted-date";
import { KeyValue } from "@/components/ui/key-value";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { secondsToApproximateString } from "@/utils/seconds";

export type FlowRunGraphSelectionPanelProps = {
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
		<div className="absolute top-4 right-4 w-72 bg-card border border-border rounded-lg shadow-lg p-4 overflow-auto max-h-[calc(100%-2rem)] z-10">
			<div className="flex justify-end mb-2">
				<Button
					variant="ghost"
					size="icon"
					onClick={onClose}
					aria-label="Close panel"
				>
					<X className="size-4" />
				</Button>
			</div>
			<Suspense fallback={<SelectionPanelSkeleton />}>
				{selection.kind === "task-run" ? (
					<TaskRunDetails selection={selection} />
				) : (
					<FlowRunDetails selection={selection} />
				)}
			</Suspense>
		</div>
	);
}

function SelectionPanelSkeleton() {
	return (
		<div className="space-y-4">
			<Skeleton className="h-6 w-3/4" />
			<div className="space-y-3">
				<Skeleton className="h-4 w-full" />
				<Skeleton className="h-4 w-full" />
				<Skeleton className="h-4 w-full" />
				<Skeleton className="h-4 w-2/3" />
			</div>
		</div>
	);
}

type TaskRunDetailsProps = {
	selection: NodeSelection;
};

function TaskRunDetails({ selection }: TaskRunDetailsProps) {
	const { data: taskRun } = useSuspenseQuery(
		buildGetTaskRunQuery(selection.id),
	);

	return <TaskRunContent taskRun={taskRun} />;
}

type TaskRunContentProps = {
	taskRun: TaskRun;
};

function TaskRunContent({ taskRun }: TaskRunContentProps) {
	const duration = taskRun.estimated_run_time ?? taskRun.total_run_time ?? 0;

	return (
		<div className="space-y-4">
			<h3 className="text-base font-semibold">
				<Link
					to="/runs/task-run/$id"
					params={{ id: taskRun.id }}
					className="text-foreground hover:underline"
				>
					{taskRun.name}
				</Link>
			</h3>
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
	selection: NodeSelection;
};

function FlowRunDetails({ selection }: FlowRunDetailsProps) {
	const { data: flowRun } = useSuspenseQuery(
		buildGetFlowRunDetailsQuery(selection.id),
	);

	return <FlowRunContent flowRun={flowRun} />;
}

type FlowRunContentProps = {
	flowRun: FlowRun;
};

function FlowRunContent({ flowRun }: FlowRunContentProps) {
	const duration = flowRun.estimated_run_time ?? flowRun.total_run_time ?? 0;

	return (
		<div className="space-y-4">
			<h3 className="text-base font-semibold">
				<Link
					to="/runs/flow-run/$id"
					params={{ id: flowRun.id }}
					className="text-foreground hover:underline"
				>
					{flowRun.name}
				</Link>
			</h3>
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
