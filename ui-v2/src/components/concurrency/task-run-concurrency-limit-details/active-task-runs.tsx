import { ConcurrencyLimitTaskRunCard } from "@/components/concurrency/concurrency-limit-task-run-card";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import { useListActiveTaskRuns } from "@/hooks/use-list-active-task-runs";

type Props = {
	data: TaskRunConcurrencyLimit;
};

export const ActiveTaskRuns = ({ data }: Props) => {
	const activeTaskRuns = useListActiveTaskRuns(data.active_slots);

	if (activeTaskRuns.length === 0) {
		return (
			<p className="flex justify-center text-slate-500">No active task runs</p>
		);
	}

	return (
		<ul className="flex flex-col gap-2">
			{activeTaskRuns.map((activeTaskRun, i) => {
				const { data } = activeTaskRun;
				if (data) {
					return (
						<li key={data.taskRun.id}>
							<ConcurrencyLimitTaskRunCard
								flow={data.flow}
								flowRun={data.flowRun}
								taskRun={data.taskRun}
							/>
						</li>
					);
				}
				return (
					<Card key={i} className="p-4">
						<Skeleton className="h-4 flex-1 max-w-[--skeleton-width]" />
						<Skeleton className="mt-2 h-4 flex-1 max-w-[--skeleton-width]" />
					</Card>
				);
			})}
		</ul>
	);
};
