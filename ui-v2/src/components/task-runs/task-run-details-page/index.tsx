import { type TaskRun, buildGetTaskRunDetailsQuery } from "@/api/task-runs";
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
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useEffect } from "react";

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
	const { data: taskRun } = useSuspenseQuery(buildGetTaskRunDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Header taskRun={taskRun} />
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
					artifactsContent={<div>🚧🚧 Pardon our dust! 🚧🚧</div>}
					taskInputsContent={<div>🚧🚧 Pardon our dust! 🚧🚧</div>}
					detailsContent={<TaskRunDetails taskRun={taskRun} />}
				/>
				<div className="hidden lg:block">
					<TaskRunDetails taskRun={taskRun} />
				</div>
			</div>
		</div>
	);
};

const Header = ({ taskRun }: { taskRun: TaskRun }) => {
	return (
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
						<TooltipTrigger>
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
