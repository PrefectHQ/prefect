import type { components } from "@/api/prefect";
import { RunCard } from "@/components/ui/run-card";

type TaskRunConcurrencyLimitActiveTaskRunsProps = {
	data: Array<{
		taskRun: components["schemas"]["TaskRun"];
		flowRun?: components["schemas"]["FlowRun"] | null;
		flow?: components["schemas"]["Flow"] | null;
	}>;
};

export const TaskRunConcurrencyLimitActiveTaskRuns = ({
	data,
}: TaskRunConcurrencyLimitActiveTaskRunsProps) => {
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
