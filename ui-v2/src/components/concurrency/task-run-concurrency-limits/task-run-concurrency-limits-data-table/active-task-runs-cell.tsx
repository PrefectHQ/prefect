import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import type { CellContext } from "@tanstack/react-table";

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
