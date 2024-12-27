import type { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import type { CellContext } from "@tanstack/react-table";

type Props = CellContext<TaskRunConcurrencyLimit, Array<string>>;

export const ActiveTaskRunCells = (props: Props) => {
	const activeTaskRuns = props.getValue();
	const numActiveTaskRuns = activeTaskRuns.length;
	if (numActiveTaskRuns === 0) {
		return "None";
	}
	return numActiveTaskRuns;
};
