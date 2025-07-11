import { useSuspenseQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { buildGetFlowRunsTaskRunsCountQuery } from "@/api/task-runs";
import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";

type FlowRunTaskRunsProps = {
	flowRun: FlowRunCardData;
};

export const FlowRunTaskRuns = ({ flowRun }: FlowRunTaskRunsProps) => {
	const { data } = useSuspenseQuery(
		buildGetFlowRunsTaskRunsCountQuery([flowRun.id]),
	);

	const taskRunsCount = data[flowRun.id];

	if (taskRunsCount === undefined) {
		return null;
	}

	return (
		<div className="flex items-center gap-2">
			<Icon id="Spline" className="size-4" />
			<Typography
				variant="xsmall"
				className={clsx(taskRunsCount === 0 && "text-muted-foreground")}
			>
				{taskRunsCount} {pluralize(taskRunsCount, "Task run")}
			</Typography>
		</div>
	);
};
