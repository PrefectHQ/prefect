import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import {
	buildFilterFlowRunsQuery,
	type FlowRun,
	isPausedState,
	isRunningState,
	isStuckState,
	isTerminalState,
	useSetFlowRunState,
} from "@/api/flow-runs";
import { buildCountTaskRunsQuery } from "@/api/task-runs";
import {
	CancelFlowRunDialog,
	PauseFlowRunDialog,
	ResumeFlowRunDialog,
	RetryFlowRunDialog,
} from "@/components/flow-runs/flow-run-actions";
import { FlowIconText } from "@/components/flows/flow-icon-text";
import { Badge } from "@/components/ui/badge";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { ChangeStateDialog } from "@/components/ui/change-state-dialog";
import { useChangeStateDialog } from "@/components/ui/change-state-dialog/use-change-state-dialog";
import {
	DeleteConfirmationDialog,
	useDeleteConfirmationDialog,
} from "@/components/ui/delete-confirmation-dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { formatDate, secondsToApproximateString } from "@/utils";

type FlowRunHeaderProps = {
	flowRun: FlowRun;
	onDeleteClick: () => void;
};

export function FlowRunHeader({ flowRun, onDeleteClick }: FlowRunHeaderProps) {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();
	const {
		open: isChangeStateOpen,
		onOpenChange: setChangeStateOpen,
		openDialog: openChangeState,
	} = useChangeStateDialog();
	const [isCancelOpen, setIsCancelOpen] = useState(false);
	const [isPauseOpen, setIsPauseOpen] = useState(false);
	const [isResumeOpen, setIsResumeOpen] = useState(false);
	const [isRetryOpen, setIsRetryOpen] = useState(false);
	const { setFlowRunState, isPending: isChangingState } = useSetFlowRunState();

	const canChangeState =
		flowRun.state_type &&
		["COMPLETED", "FAILED", "CANCELLED", "CRASHED"].includes(
			flowRun.state_type,
		);

	const canCancel = isStuckState(flowRun.state_type) && flowRun.deployment_id;
	const canPause = isRunningState(flowRun.state_type) && flowRun.deployment_id;
	const canResume = isPausedState(flowRun.state_type);
	const canRetry = isTerminalState(flowRun.state_type) && flowRun.deployment_id;

	const handleChangeState = (newState: { type: string; message?: string }) => {
		setFlowRunState(
			{
				id: flowRun.id,
				state: {
					type: newState.type as
						| "COMPLETED"
						| "FAILED"
						| "CANCELLED"
						| "CRASHED",
					name: newState.type.charAt(0) + newState.type.slice(1).toLowerCase(),
					message: newState.message,
				},
				force: true,
			},
			{
				onSuccess: () => {
					toast.success("Flow run state changed");
					setChangeStateOpen(false);
				},
				onError: (error) => {
					toast.error(error.message || "Failed to change state");
				},
			},
		);
	};

	const { data: deployment } = useQuery({
		...buildDeploymentDetailsQuery(flowRun.deployment_id ?? ""),
		enabled: !!flowRun.deployment_id,
	});

	const { data: taskRunCount } = useQuery({
		...buildCountTaskRunsQuery({
			task_runs: {
				operator: "and_",
				flow_run_id: { operator: "and_", any_: [flowRun.id], is_null_: false },
			},
		}),
	});

	const { data: parentFlowRuns } = useQuery({
		...buildFilterFlowRunsQuery({
			sort: "START_TIME_DESC",
			offset: 0,
			limit: 1,
			task_runs: {
				operator: "and_",
				id: { any_: [flowRun.parent_task_run_id ?? ""] },
			},
		}),
		enabled: !!flowRun.parent_task_run_id,
	});
	const parentFlowRun = parentFlowRuns?.[0];

	const formatTaskRunCount = (count: number | undefined) => {
		if (count === undefined) return "...";
		if (count === 0) return "None";
		return `${count} Task run${count === 1 ? "" : "s"}`;
	};

	return (
		<div className="flex flex-row justify-between">
			<div className="flex flex-col gap-2 min-w-0">
				{/* Row 1 - Breadcrumb */}
				<Breadcrumb className="min-w-0">
					<BreadcrumbList className="flex-nowrap">
						<BreadcrumbItem>
							<BreadcrumbLink to="/runs" className="text-xl font-semibold">
								Runs
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						<BreadcrumbItem className="text-xl min-w-0">
							<BreadcrumbPage
								className="font-semibold truncate block"
								title={flowRun.name}
							>
								{flowRun.name}
							</BreadcrumbPage>
							{flowRun.work_pool_name && (
								<Badge variant="outline" className="ml-2 shrink-0">
									{flowRun.work_pool_name}
								</Badge>
							)}
							{flowRun.tags && flowRun.tags.length > 0 && (
								<div className="ml-2 shrink-0">
									<TagBadgeGroup tags={flowRun.tags} maxTagsDisplayed={3} />
								</div>
							)}
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>

				{/* Row 2 - Meta */}
				<div className="flex items-center gap-4 text-sm text-muted-foreground">
					{flowRun.state_type && flowRun.state_name && (
						<StateBadge type={flowRun.state_type} name={flowRun.state_name} />
					)}
					{flowRun.start_time && (
						<div className="flex items-center gap-1">
							<Icon id="Calendar" className="size-4" />
							<span>{formatDate(flowRun.start_time, "dateTimeNumeric")}</span>
						</div>
					)}
					<div className="flex items-center gap-1">
						<Icon id="Clock" className="size-4" />
						<span>
							{secondsToApproximateString(flowRun.total_run_time ?? 0)}
						</span>
					</div>
					<div
						className={`flex items-center gap-1 ${taskRunCount === 0 ? "text-muted-foreground/60" : ""}`}
					>
						<Icon id="ListTodo" className="size-4" />
						<span>{formatTaskRunCount(taskRunCount)}</span>
					</div>
				</div>

				{/* Row 3 - Relationships */}
				<div className="flex items-center gap-4 text-sm flex-wrap">
					{flowRun.flow_id && <FlowIconText flowId={flowRun.flow_id} />}
					{flowRun.deployment_id && (
						<Link
							to="/deployments/deployment/$id"
							params={{ id: flowRun.deployment_id }}
							className="flex items-center gap-1 hover:underline"
						>
							<Icon id="Rocket" className="size-4" />
							<span className="text-muted-foreground">Deployment</span>
							<span>{deployment?.name ?? "..."}</span>
						</Link>
					)}
					{flowRun.work_pool_name && (
						<Link
							to="/work-pools/work-pool/$workPoolName"
							params={{ workPoolName: flowRun.work_pool_name }}
							className="flex items-center gap-1 hover:underline"
						>
							<Icon id="Server" className="size-4" />
							<span className="text-muted-foreground">Work Pool</span>
							<span>{flowRun.work_pool_name}</span>
						</Link>
					)}
					{flowRun.work_pool_name && flowRun.work_queue_name && (
						<Link
							to="/work-pools/work-pool/$workPoolName"
							params={{ workPoolName: flowRun.work_pool_name }}
							search={{ tab: "Work Queues" }}
							className="flex items-center gap-1 hover:underline"
						>
							<Icon id="ListOrdered" className="size-4" />
							<span className="text-muted-foreground">Work Queue</span>
							<span>{flowRun.work_queue_name}</span>
						</Link>
					)}
					{parentFlowRun && (
						<Link
							to="/runs/flow-run/$id"
							params={{ id: parentFlowRun.id }}
							className="flex items-center gap-1 hover:underline"
						>
							<Icon id="Workflow" className="size-4" />
							<span className="text-muted-foreground">Parent Run</span>
							<span>{parentFlowRun.name ?? "..."}</span>
						</Link>
					)}
				</div>
			</div>

			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="p-2">
						<MoreVertical className="w-4 h-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent>
					{canCancel && (
						<DropdownMenuItem onClick={() => setIsCancelOpen(true)}>
							Cancel
						</DropdownMenuItem>
					)}
					{canPause && (
						<DropdownMenuItem onClick={() => setIsPauseOpen(true)}>
							Pause
						</DropdownMenuItem>
					)}
					{canResume && (
						<DropdownMenuItem onClick={() => setIsResumeOpen(true)}>
							Resume
						</DropdownMenuItem>
					)}
					{canRetry && (
						<DropdownMenuItem onClick={() => setIsRetryOpen(true)}>
							Retry
						</DropdownMenuItem>
					)}
					{canChangeState && (
						<DropdownMenuItem onClick={openChangeState}>
							Change state
						</DropdownMenuItem>
					)}
					{(canCancel ||
						canPause ||
						canResume ||
						canRetry ||
						canChangeState) && <DropdownMenuSeparator />}
					<DropdownMenuItem
						onClick={() => {
							void navigator.clipboard.writeText(flowRun.id);
							toast.success("Copied flow run ID to clipboard");
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() =>
							confirmDelete({
								title: "Delete Flow Run",
								description: `Are you sure you want to delete flow run ${flowRun.name}?`,
								onConfirm: onDeleteClick,
							})
						}
					>
						Delete
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			<DeleteConfirmationDialog {...dialogState} />
			<ChangeStateDialog
				open={isChangeStateOpen}
				onOpenChange={setChangeStateOpen}
				currentState={
					flowRun.state
						? {
								type: flowRun.state.type,
								name:
									flowRun.state.name ??
									flowRun.state.type.charAt(0) +
										flowRun.state.type.slice(1).toLowerCase(),
							}
						: null
				}
				label="Flow Run"
				onConfirm={handleChangeState}
				isLoading={isChangingState}
			/>
			<CancelFlowRunDialog
				flowRun={flowRun}
				open={isCancelOpen}
				onOpenChange={setIsCancelOpen}
			/>
			<PauseFlowRunDialog
				flowRun={flowRun}
				open={isPauseOpen}
				onOpenChange={setIsPauseOpen}
			/>
			<ResumeFlowRunDialog
				flowRun={flowRun}
				open={isResumeOpen}
				onOpenChange={setIsResumeOpen}
			/>
			<RetryFlowRunDialog
				flowRun={flowRun}
				open={isRetryOpen}
				onOpenChange={setIsRetryOpen}
			/>
		</div>
	);
}
