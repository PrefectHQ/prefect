import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { queryKeyFactory as artifactsQueryKeyFactory } from "@/api/artifacts";
import {
	buildGetFlowRunDetailsQuery,
	type FlowRun,
	queryKeyFactory as flowRunsQueryKeyFactory,
	useDeleteFlowRun,
	useSetFlowRunState,
} from "@/api/flow-runs";
import { queryKeyFactory as logsQueryKeyFactory } from "@/api/logs";
import { queryKeyFactory as taskRunsQueryKeyFactory } from "@/api/task-runs";
import { FlowRunGraph } from "@/components/flow-runs/flow-run-graph";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	ChangeStateDialog,
	useChangeStateDialog,
} from "@/components/ui/change-state-dialog";
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
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Icon } from "@/components/ui/icons";
import { LazyJsonInput } from "@/components/ui/json-input-lazy";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { TabErrorState } from "@/components/ui/tab-error-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FlowRunArtifacts } from "./flow-run-artifacts";
import { FlowRunDetails } from "./flow-run-details";
import { FlowRunLogs } from "./flow-run-logs";
import { FlowRunSubflows } from "./flow-run-subflows";
import { FlowRunTaskRuns } from "./flow-run-task-runs";

type FlowRunDetailsTabOptions =
	| "Logs"
	| "TaskRuns"
	| "SubflowRuns"
	| "Artifacts"
	| "Details"
	| "Parameters"
	| "JobVariables";

type FlowRunDetailsPageProps = {
	id: string;
	tab: FlowRunDetailsTabOptions;
	onTabChange: (tab: FlowRunDetailsTabOptions) => void;
};

export const FlowRunDetailsPage = ({
	id,
	tab,
	onTabChange,
}: FlowRunDetailsPageProps) => {
	const [refetchInterval, setRefetchInterval] = useState<number | false>(false);
	const [fullscreen, setFullscreen] = useState(false);
	const queryClient = useQueryClient();
	const { data: flowRun } = useSuspenseQuery({
		...buildGetFlowRunDetailsQuery(id),
		refetchInterval,
	});
	const { deleteFlowRun } = useDeleteFlowRun();
	const { navigate } = useRouter();
	const isPending = flowRun.state_type === "PENDING";

	useEffect(() => {
		if (flowRun.state_type === "RUNNING" || flowRun.state_type === "PENDING") {
			setRefetchInterval(5000);
		} else {
			setRefetchInterval(false);
		}
	}, [flowRun]);

	const onDeleteRunClicked = () => {
		deleteFlowRun(flowRun.id, {
			onSuccess: () => {
				setRefetchInterval(false);
				toast.success("Flow run deleted");
				void navigate({ to: "/runs", replace: true });
			},
			onError: (error) => {
				const message =
					error.message || "Unknown error while deleting flow run.";
				toast.error(message);
			},
		});
	};

	const retryLogs = useCallback(() => {
		void queryClient.invalidateQueries({
			queryKey: logsQueryKeyFactory.all(),
		});
	}, [queryClient]);

	const retryTaskRuns = useCallback(() => {
		void queryClient.invalidateQueries({
			queryKey: taskRunsQueryKeyFactory.all(),
		});
	}, [queryClient]);

	const retrySubflows = useCallback(() => {
		void queryClient.invalidateQueries({
			queryKey: flowRunsQueryKeyFactory.lists(),
		});
	}, [queryClient]);

	const retryArtifacts = useCallback(() => {
		void queryClient.invalidateQueries({
			queryKey: artifactsQueryKeyFactory.all(),
		});
	}, [queryClient]);

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Header flowRun={flowRun} onDeleteRunClicked={onDeleteRunClicked} />
			</div>
			{!isPending && (
				<Card>
					<CardContent className="p-0">
						<FlowRunGraph
							flowRunId={flowRun.id}
							fullscreen={fullscreen}
							onFullscreenChange={setFullscreen}
						/>
					</CardContent>
				</Card>
			)}
			<div className="grid lg:grid-cols-[1fr_250px] grid-cols-[1fr] gap-4">
				<TabsLayout
					currentTab={tab}
					onTabChange={onTabChange}
					flowRun={flowRun}
					logsContent={
						<ErrorBoundary
							fallback={
								<TabErrorState
									error={{
										type: "unknown-error",
										message: "Failed to load logs",
										details:
											"An error occurred while loading log data. Please try again.",
									}}
									onRetry={retryLogs}
								/>
							}
						>
							<Suspense fallback={<LogsSkeleton />}>
								<FlowRunLogs flowRun={flowRun} />
							</Suspense>
						</ErrorBoundary>
					}
					taskRunsContent={
						<ErrorBoundary
							fallback={
								<TabErrorState
									error={{
										type: "unknown-error",
										message: "Failed to load task runs",
										details:
											"An error occurred while loading task run data. Please try again.",
									}}
									onRetry={retryTaskRuns}
								/>
							}
						>
							<Suspense fallback={<TaskRunsSkeleton />}>
								<FlowRunTaskRuns flowRunId={id} />
							</Suspense>
						</ErrorBoundary>
					}
					subflowRunsContent={
						<ErrorBoundary
							fallback={
								<TabErrorState
									error={{
										type: "unknown-error",
										message: "Failed to load subflow runs",
										details:
											"An error occurred while loading subflow run data. Please try again.",
									}}
									onRetry={retrySubflows}
								/>
							}
						>
							<Suspense fallback={<SubflowsSkeleton />}>
								<FlowRunSubflows parentFlowRunId={id} />
							</Suspense>
						</ErrorBoundary>
					}
					artifactsContent={
						<ErrorBoundary
							fallback={
								<TabErrorState
									error={{
										type: "unknown-error",
										message: "Failed to load artifacts",
										details:
											"An error occurred while loading artifact data. Please try again.",
									}}
									onRetry={retryArtifacts}
								/>
							}
						>
							<Suspense fallback={<ArtifactsSkeleton />}>
								<FlowRunArtifacts flowRun={flowRun} />
							</Suspense>
						</ErrorBoundary>
					}
					detailsContent={
						<Suspense fallback={<DetailsSkeleton />}>
							<FlowRunDetails flowRun={flowRun} />
						</Suspense>
					}
					parametersContent={
						<div className="space-y-4">
							<div className="flex justify-end">
								<Button
									variant="outline"
									size="sm"
									onClick={() => {
										toast.success("Copied parameters to clipboard");
										void navigator.clipboard.writeText(
											JSON.stringify(flowRun.parameters ?? {}, null, 2),
										);
									}}
								>
									<Icon id="Copy" className="size-4 mr-2" />
									Copy parameters
								</Button>
							</div>
							<LazyJsonInput
								value={JSON.stringify(flowRun.parameters ?? {}, null, 2)}
								disabled
								className="min-h-[200px]"
							/>
						</div>
					}
					jobVariablesContent={
						<div className="space-y-4">
							<div className="flex justify-end">
								<Button
									variant="outline"
									size="sm"
									onClick={() => {
										toast.success("Copied job variables to clipboard");
										void navigator.clipboard.writeText(
											JSON.stringify(flowRun.job_variables ?? {}, null, 2),
										);
									}}
								>
									<Icon id="Copy" className="size-4 mr-2" />
									Copy job variables
								</Button>
							</div>
							<LazyJsonInput
								value={JSON.stringify(flowRun.job_variables ?? {}, null, 2)}
								disabled
								className="min-h-[200px]"
							/>
						</div>
					}
				/>
				<div className="hidden lg:block">
					<FlowRunDetails flowRun={flowRun} />
				</div>
			</div>
		</div>
	);
};

const Header = ({
	flowRun,
	onDeleteRunClicked,
}: {
	flowRun: FlowRun;
	onDeleteRunClicked: () => void;
}) => {
	const [dialogState, confirmDelete] = useDeleteConfirmationDialog();
	const {
		open: isChangeStateOpen,
		onOpenChange: setChangeStateOpen,
		openDialog: openChangeState,
	} = useChangeStateDialog();
	const { setFlowRunState, isPending: isChangingState } = useSetFlowRunState();

	const canChangeState =
		flowRun.state_type &&
		["COMPLETED", "FAILED", "CANCELLED", "CRASHED"].includes(
			flowRun.state_type,
		);

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
					<BreadcrumbItem className="text-xl">
						<BreadcrumbPage className="font-semibold">
							{flowRun.name}
						</BreadcrumbPage>
						{flowRun.state && (
							<StateBadge
								type={flowRun.state.type}
								name={flowRun.state.name}
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
					{canChangeState && (
						<DropdownMenuItem onClick={openChangeState}>
							Change state
						</DropdownMenuItem>
					)}
					<DropdownMenuItem
						onClick={() => {
							toast.success("Copied flow run ID to clipboard");
							void navigator.clipboard.writeText(flowRun.id);
						}}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuItem
						onClick={() =>
							confirmDelete({
								title: "Delete Flow Run",
								description: `Are you sure you want to delete flow run ${flowRun.name}?`,
								onConfirm: onDeleteRunClicked,
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
		</div>
	);
};

const TabsLayout = ({
	currentTab,
	onTabChange,
	flowRun,
	logsContent,
	taskRunsContent,
	subflowRunsContent,
	artifactsContent,
	detailsContent,
	parametersContent,
	jobVariablesContent,
}: {
	currentTab: FlowRunDetailsTabOptions;
	onTabChange: (tab: FlowRunDetailsTabOptions) => void;
	flowRun: FlowRun;
	logsContent: React.ReactNode;
	taskRunsContent: React.ReactNode;
	subflowRunsContent: React.ReactNode;
	artifactsContent: React.ReactNode;
	detailsContent: React.ReactNode;
	parametersContent: React.ReactNode;
	jobVariablesContent: React.ReactNode;
}) => {
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
			onValueChange={(value) => onTabChange(value as FlowRunDetailsTabOptions)}
		>
			<TabsList>
				<TabsTrigger value="Details" className="lg:hidden">
					Details
				</TabsTrigger>
				<TabsTrigger value="Logs">Logs</TabsTrigger>
				{flowRun.state_type !== "PENDING" && (
					<TabsTrigger value="TaskRuns">Task Runs</TabsTrigger>
				)}
				{flowRun.state_type !== "PENDING" && (
					<TabsTrigger value="SubflowRuns">Subflow Runs</TabsTrigger>
				)}
				<TabsTrigger value="Artifacts">Artifacts</TabsTrigger>
				<TabsTrigger value="Parameters">Parameters</TabsTrigger>
				<TabsTrigger value="JobVariables">Job Variables</TabsTrigger>
			</TabsList>
			<TabsContent value="Details">{detailsContent}</TabsContent>
			<TabsContent value="Logs">{logsContent}</TabsContent>
			<TabsContent value="TaskRuns">{taskRunsContent}</TabsContent>
			<TabsContent value="SubflowRuns">{subflowRunsContent}</TabsContent>
			<TabsContent value="Artifacts">{artifactsContent}</TabsContent>
			<TabsContent value="Parameters">{parametersContent}</TabsContent>
			<TabsContent value="JobVariables">{jobVariablesContent}</TabsContent>
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

const TaskRunsSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<Skeleton className="h-4 w-24" />
			</div>
			<div className="flex flex-col sm:flex-row gap-2">
				<Skeleton className="h-9 flex-1" />
				<div className="flex gap-2">
					<Skeleton className="h-9 w-48" />
					<Skeleton className="h-9 w-40" />
				</div>
			</div>
			<div className="flex flex-col gap-2">
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
			</div>
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

const SubflowsSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<Skeleton className="h-4 w-24" />
			</div>
			<div className="flex flex-col sm:flex-row gap-2">
				<Skeleton className="h-9 flex-1" />
				<div className="flex gap-2">
					<Skeleton className="h-9 w-48" />
					<Skeleton className="h-9 w-40" />
				</div>
			</div>
			<div className="flex flex-col gap-2">
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
			</div>
		</div>
	);
};

const DetailsSkeleton = () => {
	return (
		<div className="space-y-4">
			<div className="flex flex-col gap-1">
				<Skeleton className="h-4 w-20" />
				<Skeleton className="h-5 w-12" />
			</div>
			<div className="flex flex-col gap-1">
				<Skeleton className="h-4 w-16" />
				<Skeleton className="h-5 w-32" />
			</div>
			<div className="flex flex-col gap-1">
				<Skeleton className="h-4 w-24" />
				<Skeleton className="h-5 w-32" />
			</div>
			<div className="flex flex-col gap-1">
				<Skeleton className="h-4 w-24" />
				<Skeleton className="h-5 w-64" />
			</div>
		</div>
	);
};
