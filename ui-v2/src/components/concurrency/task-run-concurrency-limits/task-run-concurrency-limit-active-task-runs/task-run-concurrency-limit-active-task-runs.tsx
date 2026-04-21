import type { components } from "@/api/prefect";
import { RunCard } from "@/components/ui/run-card";

type TaskRunConcurrencyLimitActiveTaskRunsProps = {
	data: Array<{
		taskRun: components["schemas"]["TaskRun"];
		flowRun?: components["schemas"]["FlowRunResponse"] | null;
		flow?: components["schemas"]["Flow"] | null;
	}>;
};

export const TaskRunConcurrencyLimitActiveTaskRuns = ({
	data,
}: TaskRunConcurrencyLimitActiveTaskRunsProps) => {
	if (data.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center gap-3 p-4 text-center text-sm text-muted-foreground">
				No active task runs
			</div>
		);
	}

	return (
		<ul className="flex flex-col gap-2">
			{data.map((d) => (
				<li key={d.taskRun.id}>
					<RunCard flow={d.flow} flowRun={d.flowRun} taskRun={d.taskRun} />
				</li>
			))}
		</ul>
	);
};
