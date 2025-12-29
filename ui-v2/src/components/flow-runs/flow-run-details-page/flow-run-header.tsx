import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { toast } from "sonner";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import { buildFLowDetailsQuery } from "@/api/flows";
import { buildCountTaskRunsQuery } from "@/api/task-runs";
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
import {
	DeleteConfirmationDialog,
	useDeleteConfirmationDialog,
} from "@/components/ui/delete-confirmation-dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { formatDate, secondsToApproximateString } from "@/utils";

type FlowRunHeaderProps = {
	flowRun: FlowRun;
	onDeleteClick: () => void;
};

export function FlowRunHeader({ flowRun, onDeleteClick }: FlowRunHeaderProps) {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();

	const { data: flow } = useQuery({
		...buildFLowDetailsQuery(flowRun.flow_id),
		enabled: !!flowRun.flow_id,
	});

	const { data: deployment } = useQuery({
		...buildDeploymentDetailsQuery(flowRun.deployment_id ?? ""),
		enabled: !!flowRun.deployment_id,
	});

	const { data: taskRunCount } = useQuery({
		...buildCountTaskRunsQuery({
			task_runs: { flow_run_id: { any_: [flowRun.id] } },
		}),
	});

	const formatTaskRunCount = (count: number | undefined) => {
		if (count === undefined) return "...";
		if (count === 0) return "None";
		return `${count} Task run${count === 1 ? "" : "s"}`;
	};

	return (
		<div className="flex flex-row justify-between">
			<div className="flex flex-col gap-2">
				{/* Row 1 - Breadcrumb */}
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem>
							<BreadcrumbLink to="/runs" className="text-xl font-semibold">
								Runs
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						<BreadcrumbItem className="text-xl">
							<BreadcrumbPage className="font-semibold">
								{flowRun.name}
							</BreadcrumbPage>
							{flowRun.work_pool_name && (
								<Badge variant="outline" className="ml-2">
									{flowRun.work_pool_name}
								</Badge>
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
				<div className="flex items-center gap-4 text-sm">
					{flowRun.flow_id && (
						<Link
							to="/flows/flow/$id"
							params={{ id: flowRun.flow_id }}
							className="flex items-center gap-1 hover:underline"
						>
							<Icon id="Workflow" className="size-4" />
							<span className="text-muted-foreground">Flow</span>
							<span>{flow?.name ?? "..."}</span>
						</Link>
					)}
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
				</div>
			</div>

			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="p-2">
						<MoreVertical className="w-4 h-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent>
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
		</div>
	);
}
