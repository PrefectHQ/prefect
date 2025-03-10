import { TaskRun } from "@/api/task-runs";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";
import { useMemo } from "react";

type TaskRunSectionProps = {
	taskRun: TaskRun;
};

export const TaskRunSection = ({ taskRun }: TaskRunSectionProps) => {
	const taskRunCreated = useMemo(() => {
		const date = new Date(taskRun.created ?? "");
		return formatDate(date, "dateTime");
	}, [taskRun.created]);

	const taskRunUpdated = useMemo(() => {
		const date = new Date(taskRun.updated ?? "");
		return formatDate(date, "dateTime");
	}, [taskRun.updated]);

	return (
		<div className="mt-4">
			<Typography variant="bodyLarge" className="font-bold">
				Task Run
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Created
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{taskRunCreated ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Last Updated
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{taskRunUpdated ?? " "}
			</Typography>
			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Tags
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="text-muted-foreground mt-1 flex items-center"
			>
				{(taskRun.tags?.length ?? 0 > 0)
					? taskRun.tags?.map((tag) => (
							<span key={tag} className="bg-gray-100 p-1 mx-1 mt-1 rounded">
								{tag}
							</span>
						))
					: "None"}
			</Typography>
		</div>
	);
};
