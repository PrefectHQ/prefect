import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import {
	buildCountTaskRunsQuery,
	buildListTaskRunsQuery,
} from "@/api/task-runs";
import {
	TaskRunsList,
	TaskRunsRowCount,
	useTaskRunsSelectedRows,
} from "@/components/task-runs/task-runs-list";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";

const searchParams = z.object({
	tab: z
		.enum(["flow-runs", "task-runs"])
		.default("task-runs")
		.catch("task-runs"),
	taskRunsOffset: z.number().int().nonnegative().optional().default(0),
	taskRunsLimit: z.number().int().positive().optional().default(50),
});

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search: { taskRunsOffset, taskRunsLimit } }) => ({
		taskRunsOffset,
		taskRunsLimit,
	}),
	loader: async ({ context: { queryClient }, deps }) => {
		const taskRunsFilter = {
			offset: deps.taskRunsOffset,
			limit: deps.taskRunsLimit,
			sort: "EXPECTED_START_TIME_DESC" as const,
		};
		await Promise.all([
			queryClient.ensureQueryData(buildListTaskRunsQuery(taskRunsFilter)),
			queryClient.ensureQueryData(buildCountTaskRunsQuery({})),
		]);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { tab } = Route.useSearch();
	const navigate = useNavigate();

	const handleTabChange = (value: string) => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				tab: value as "flow-runs" | "task-runs",
			}),
		});
	};

	return (
		<div className="flex flex-col gap-4 p-4">
			<Typography variant="h2">Runs</Typography>
			<Tabs value={tab} onValueChange={handleTabChange}>
				<TabsList>
					<TabsTrigger value="flow-runs">Flow Runs</TabsTrigger>
					<TabsTrigger value="task-runs">Task Runs</TabsTrigger>
				</TabsList>
				<TabsContent value="flow-runs">
					<div className="py-4">
						<Typography variant="bodySmall" className="text-muted-foreground">
							Flow runs tab coming soon
						</Typography>
					</div>
				</TabsContent>
				<TabsContent value="task-runs">
					<TaskRunsTab />
				</TabsContent>
			</Tabs>
		</div>
	);
}

function TaskRunsTab() {
	const { taskRunsOffset, taskRunsLimit } = Route.useSearch();

	const taskRunsFilter = {
		offset: taskRunsOffset,
		limit: taskRunsLimit,
		sort: "EXPECTED_START_TIME_DESC" as const,
	};

	const { data: taskRuns } = useSuspenseQuery(
		buildListTaskRunsQuery(taskRunsFilter),
	);
	const { data: taskRunsCount } = useSuspenseQuery(buildCountTaskRunsQuery({}));

	const [selectedRows, setSelectedRows, { onSelectRow }] =
		useTaskRunsSelectedRows();

	return (
		<div className="flex flex-col gap-4 py-4">
			<div className="flex items-center justify-between">
				<TaskRunsRowCount
					count={taskRunsCount}
					results={taskRuns}
					selectedRows={selectedRows}
					setSelectedRows={setSelectedRows}
				/>
			</div>
			<TaskRunsList
				taskRuns={taskRuns}
				selectedRows={selectedRows}
				onSelect={onSelectRow}
			/>
		</div>
	);
}
