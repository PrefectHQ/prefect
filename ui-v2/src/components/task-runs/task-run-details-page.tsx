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
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
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
			<div className="flex flex-col gap-4">
				<Tabs
					value={tab}
					onValueChange={(value) =>
						onTabChange(value as TaskRunDetailsTabOptions)
					}
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
					<TabsContent value="Logs">
						<Suspense fallback={<div>Loading...</div>}>
							<TaskRunLogs taskRun={taskRun} />
						</Suspense>
					</TabsContent>
				</Tabs>
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
