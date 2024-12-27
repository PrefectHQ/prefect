import type { components } from "@/api/prefect";
import { RunCard } from "@/components/ui/run-card";

type Props = {
	data: Array<{
		taskRun: components["schemas"]["TaskRun"];
		flowRun?: components["schemas"]["FlowRun"];
		flow?: components["schemas"]["Flow"];
	}>;
};

export const TaskRunConcurrencyLimitActiveTaskRuns = ({ data }: Props) => {
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
