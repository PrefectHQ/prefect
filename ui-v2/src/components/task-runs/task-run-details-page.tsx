import { type TaskRun, buildGetTaskRunDetailsQuery } from "@/api/task-runs";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense } from "react";
import { Icon } from "../ui/icons";
import { Skeleton } from "../ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { TaskRunDetails } from "./task-run-details/task-run-details";
import { TaskRunLogs } from "./task-run-logs";

type TaskRunDetailsPageProps = {
	id: string;
	tab: TaskRunDetailsTabOptions;
	onTabChange: (tab: TaskRunDetailsTabOptions) => void;
};

type TaskRunDetailsTabOptions = "Logs" | "Artifacts" | "TaskInputs";

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
			<div className="grid grid-cols-[1fr_250px] gap-4">
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
				/>
				<TaskRunDetails taskRun={taskRun} />
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
								{taskRun.flow_run_id}
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
					</>
				)}
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{taskRun.name}</BreadcrumbPage>
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
}: {
	currentTab: TaskRunDetailsTabOptions;
	onTabChange: (tab: TaskRunDetailsTabOptions) => void;
	logsContent: React.ReactNode;
	artifactsContent: React.ReactNode;
	taskInputsContent: React.ReactNode;
}) => {
	return (
		<Tabs
			value={currentTab}
			onValueChange={(value) => onTabChange(value as TaskRunDetailsTabOptions)}
		>
			<TabsList>
				<TabsTrigger value="Logs" className="px-8">
					Logs
				</TabsTrigger>
				<TabsTrigger value="Artifacts" className="px-8">
					Artifacts
				</TabsTrigger>
				<TabsTrigger value="TaskInputs" className="px-8">
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
