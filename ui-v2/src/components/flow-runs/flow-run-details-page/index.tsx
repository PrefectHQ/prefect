import { useSuspenseQuery } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { MoreVertical } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
	buildGetFlowRunDetailsQuery,
	type FlowRun,
	useDeleteFlowRun,
	useSetFlowRunState,
} from "@/api/flow-runs";
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
import { StateBadge } from "@/components/ui/state-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
	const { data: flowRun } = useSuspenseQuery({
		...buildGetFlowRunDetailsQuery(id),
		refetchInterval,
	});
	const { deleteFlowRun } = useDeleteFlowRun();
	const { navigate } = useRouter();

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

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Header flowRun={flowRun} onDeleteRunClicked={onDeleteRunClicked} />
			</div>
			<div className="grid lg:grid-cols-[1fr_250px] grid-cols-[1fr] gap-4">
				<TabsLayout
					currentTab={tab}
					onTabChange={onTabChange}
					logsContent={<PlaceholderContent label="Logs" />}
					taskRunsContent={<PlaceholderContent label="Task Runs" />}
					subflowRunsContent={<PlaceholderContent label="Subflow Runs" />}
					artifactsContent={<PlaceholderContent label="Artifacts" />}
					detailsContent={<PlaceholderContent label="Details" />}
					parametersContent={<PlaceholderContent label="Parameters" />}
					jobVariablesContent={<PlaceholderContent label="Job Variables" />}
				/>
				<FlowRunDetailsSidebar flowRun={flowRun} />
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
				<TabsTrigger value="TaskRuns">Task Runs</TabsTrigger>
				<TabsTrigger value="SubflowRuns">Subflow Runs</TabsTrigger>
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

const FlowRunDetailsSidebar = ({ flowRun }: { flowRun: FlowRun }) => {
	return (
		<div className="hidden lg:block">
			<div className="rounded-lg border p-4">
				<h3 className="font-semibold mb-4">Details</h3>
				<div className="space-y-3 text-sm">
					<div>
						<span className="text-muted-foreground">Flow Run ID</span>
						<p className="font-mono text-xs break-all">{flowRun.id}</p>
					</div>
					{flowRun.flow_id && (
						<div>
							<span className="text-muted-foreground">Flow ID</span>
							<p className="font-mono text-xs break-all">{flowRun.flow_id}</p>
						</div>
					)}
					{flowRun.deployment_id && (
						<div>
							<span className="text-muted-foreground">Deployment ID</span>
							<p className="font-mono text-xs break-all">
								{flowRun.deployment_id}
							</p>
						</div>
					)}
					{flowRun.start_time && (
						<div>
							<span className="text-muted-foreground">Start Time</span>
							<p>{new Date(flowRun.start_time).toLocaleString()}</p>
						</div>
					)}
					{flowRun.end_time && (
						<div>
							<span className="text-muted-foreground">End Time</span>
							<p>{new Date(flowRun.end_time).toLocaleString()}</p>
						</div>
					)}
					{flowRun.total_run_time !== undefined &&
						flowRun.total_run_time > 0 && (
							<div>
								<span className="text-muted-foreground">Duration</span>
								<p>{flowRun.total_run_time.toFixed(2)}s</p>
							</div>
						)}
					{flowRun.tags && flowRun.tags.length > 0 && (
						<div>
							<span className="text-muted-foreground">Tags</span>
							<div className="flex flex-wrap gap-1 mt-1">
								{flowRun.tags.map((tag) => (
									<span
										key={tag}
										className="px-2 py-0.5 bg-muted rounded text-xs"
									>
										{tag}
									</span>
								))}
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

const PlaceholderContent = ({ label }: { label: string }) => {
	return (
		<div className="flex items-center justify-center h-48 border rounded-lg bg-muted/50">
			<p className="text-muted-foreground">
				{label} content will be added here
			</p>
		</div>
	);
};
