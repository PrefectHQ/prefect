import type { CellContext } from "@tanstack/react-table";
import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";

type ActiveTaskRunCellsProps = CellContext<
	TaskRunConcurrencyLimit,
	Array<string>
>;

export const ActiveTaskRunCells = (props: ActiveTaskRunCellsProps) => {
	const activeTaskRuns = props.getValue();
	const numActiveTaskRuns = activeTaskRuns.length;
	if (numActiveTaskRuns === 0) {
		return "None";
	}
	return numActiveTaskRuns;
};
