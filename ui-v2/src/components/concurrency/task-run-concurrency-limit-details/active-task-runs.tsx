import { components } from "@/api/prefect";
import { ConcurrencyLimitTaskRunCard } from "@/components/concurrency/concurrency-limit-task-run-card";

type Props = {
	data: Array<{
		taskRun: components["schemas"]["TaskRun"];
		flowRun: components["schemas"]["FlowRun"];
		flow: components["schemas"]["Flow"];
	}>;
};

export const ActiveTaskRuns = ({ data }: Props) => {
	if (data.length === 0) {
		return (
			<p className="flex justify-center text-slate-500">No active task runs</p>
		);
	}

	return (
		<ul className="flex flex-col gap-2">
			{data.map((d) => {
				return (
					<li key={d.taskRun.id}>
						<ConcurrencyLimitTaskRunCard
							flow={d.flow}
							flowRun={d.flowRun}
							taskRun={d.taskRun}
						/>
					</li>
				);
			})}
		</ul>
	);
};
