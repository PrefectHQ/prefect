import { useSuspenseQuery } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";
import {
	buildGetTaskRunDetailsQuery,
	type TaskRun,
	useDeleteTaskRun,
} from "@/api/task-runs";
import { TaskRunArtifacts } from "@/components/task-runs/task-run-artifacts";
import { TaskRunDetails } from "@/components/task-runs/task-run-details/task-run-details";
import { TaskRunLogs } from "@/components/task-runs/task-run-logs";
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
import { JsonInput } from "@/components/ui/json-input";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";

type TaskRunDetailsPageProps = {
	id: string;
	tab: TaskRunDetailsTabOptions;
	onTabChange: (tab: TaskRunDetailsTabOptions) => void;
};

type TaskRunDetailsTabOptions = "Logs" | "Artifacts" | "TaskInputs" | "Details";

export const TaskRunDetailsPage = ({
	id,
	tab,
	onTabChange,
}: TaskRunDetailsPageProps) => {
	const [refetchInterval, setRefetchInterval] = useState<number | false>(false);
	const { data: taskRun } = useSuspenseQuery({
		...buildGetTaskRunDetailsQuery(id),
		refetchInterval,
	});
	const { deleteTaskRun } = useDeleteTaskRun();
	const { navigate } = useRouter();

	useEffect(() => {
		if (taskRun.state_type === "RUNNING" || taskRun.state_type === "PENDING") {
			setRefetchInterval(5000);
		} else {
			setRefetchInterval(false);
		}
	}, [taskRun]);

	const onDeleteRunClicked = () => {
		deleteTaskRun(
			{ id: taskRun.id },
			{
				onSuccess: () => {
					setRefetchInterval(false);
					toast.success("Task run deleted");
					if (taskRun.flow_run_id) {
						void navigate({
							to: "/runs/flow-run/$id",
							params: { id: taskRun.flow_run_id },
							replace: true,
						});
					} else {
						void navigate({ to: "/runs", replace: true });
					}
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while deleting task run.";
					toast.error(message);
				},
			},
		);
	};
	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Header taskRun={taskRun} onDeleteRunClicked={onDeleteRunClicked} />
			</div>
			<div className="grid lg:grid-cols-[1fr_250px] grid-cols-[1fr] gap-4">
				<TabsLayout
					currentTab={tab}
					onTabChange={onTabChange}
					logsContent={
						<Suspense fallback={<LogsSkeleton />}>
							<TaskRunLogs taskRun={taskRun} />
						</Suspense>
					}
					artifactsContent={
						<Suspense fallback={<ArtifactsSkeleton />}>
							<TaskRunArtifacts taskRun={taskRun} />
						</Suspense>
					}
					taskInputsContent={<TaskInputs taskRun={taskRun} />}
					detailsContent={<TaskRunDetails taskRun={taskRun} />}
				/>
				<div className="hidden lg:block">
					<TaskRunDetails taskRun={taskRun} />
				</div>
			</div>
		</div>
	);
};

const Header = ({
	taskRun,
	onDeleteRunClicked,
}: {
	taskRun: TaskRun;
	onDeleteRunClicked: () => void;
}) => {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();
	return (
		<div className="flex flex-row justify-between">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<BreadcrumbLink to="/runs" className="text-xl font-semibold">
							Runs
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					{taskRun.flow_run_id && (
						<>
							<BreadcrumbItem>
								<BreadcrumbLink
									to="/runs/flow-run/$id"
									params={{ id: taskRun.flow_run_id }}
									className="text-xl font-semibold"
								>
									{taskRun.flow_run_name}
								</BreadcrumbLink>
							</BreadcrumbItem>
							<BreadcrumbSeparator />
						</>
					)}
					<BreadcrumbItem className="text-xl">
						<BreadcrumbPage className="font-semibold">
							{taskRun.name}
						</BreadcrumbPage>
						{taskRun.state && (
							<StateBadge
								type={taskRun.state.type}
								name={taskRun.state.name}
								className="ml-2"
							/>
						)}
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="p-2">
						<MoreVertical className="w-4 h-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent>
					<DropdownMenuItem
						onClick={() => {
							alert("Still working on this");
						}}
					>
						Change state
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() => {
							toast.success("Copied task run ID to clipboard");
							void navigator.clipboard.writeText(taskRun.id);
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() =>
							confirmDelete({
								title: "Delete Task Run",
								description: `Are you sure you want to delete task run ${taskRun.name}?`,
								onConfirm: onDeleteRunClicked,
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
};

const TabsLayout = ({
	currentTab,
	onTabChange,
	logsContent,
	artifactsContent,
	taskInputsContent,
	detailsContent,
}: {
	currentTab: TaskRunDetailsTabOptions;
	onTabChange: (tab: TaskRunDetailsTabOptions) => void;
	logsContent: React.ReactNode;
	artifactsContent: React.ReactNode;
	taskInputsContent: React.ReactNode;
	detailsContent: React.ReactNode;
}) => {
	// Change tab on screen size change when the details tab is selected
	useEffect(() => {
		const bp = getComputedStyle(document.documentElement)
			.getPropertyValue("--breakpoint-lg")
			.trim();
		const mql = window.matchMedia(`(max-width: ${bp})`);
		const onChange = () => {
			if (currentTab === "Details") {
				onTabChange("Logs");
			}
		};
		mql.addEventListener("change", onChange);
		return () => mql.removeEventListener("change", onChange);
	}, [currentTab, onTabChange]);

	return (
		<Tabs
			value={currentTab}
			onValueChange={(value) => onTabChange(value as TaskRunDetailsTabOptions)}
		>
			<TabsList>
				<TabsTrigger value="Details" className="lg:hidden">
					Details
				</TabsTrigger>
				<TabsTrigger value="Logs">Logs</TabsTrigger>
				<TabsTrigger value="Artifacts">Artifacts</TabsTrigger>
				<TabsTrigger value="TaskInputs">
					Task Inputs
					<Tooltip>
						<TooltipTrigger asChild>
							<Icon id="Info" className="w-4 h-4" />
						</TooltipTrigger>
						<TooltipContent>
							Task inputs show parameter keys and can also show task run
							relationships.
						</TooltipContent>
					</Tooltip>
				</TabsTrigger>
			</TabsList>
			<TabsContent value="Details">{detailsContent}</TabsContent>
			<TabsContent value="Logs">{logsContent}</TabsContent>
			<TabsContent value="Artifacts">{artifactsContent}</TabsContent>
			<TabsContent value="TaskInputs">{taskInputsContent}</TabsContent>
		</Tabs>
	);
};

const LogsSkeleton = () => {
	return (
		<div className="flex flex-col gap-2">
			<div className="flex flex-row gap-2 justify-end">
				<Skeleton className="h-8 w-25" />
				<Skeleton className="h-8 w-32" />
			</div>
			<Skeleton className="h-32" />
		</div>
	);
};

const ArtifactsSkeleton = () => {
	return (
		<div className="flex flex-col gap-2">
			<div className="flex flex-row justify-end">
				<Skeleton className="h-8 w-12" />
			</div>

			<div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
				<Skeleton className="h-40" />
				<Skeleton className="h-40" />
				<Skeleton className="h-40" />
				<Skeleton className="h-40" />
			</div>
		</div>
	);
};

const TaskInputs = ({ taskRun }: { taskRun: TaskRun }) => {
	return (
		<JsonInput value={JSON.stringify(taskRun.task_inputs, null, 2)} disabled />
	);
};
