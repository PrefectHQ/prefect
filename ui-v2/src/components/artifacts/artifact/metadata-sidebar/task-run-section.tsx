import { useMemo } from "react";
import type { TaskRun } from "@/api/task-runs";
import { TagBadge } from "@/components/ui/tag-badge";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";

type TaskRunSectionProps = {
	taskRun: TaskRun;
};

export const TaskRunSection = ({ taskRun }: TaskRunSectionProps) => {
	const createdDate = useMemo(() => {
		if (!taskRun.created) return null;
		return formatDate(taskRun.created, "dateTime");
	}, [taskRun.created]);

	const updatedDate = useMemo(() => {
		if (!taskRun.updated) return null;
		return formatDate(taskRun.updated, "dateTime");
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
				className="mt-1 text-foreground"
			>
				{createdDate ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Last Updated
			</Typography>
			<Typography
				variant="bodySmall"
				fontFamily="mono"
				className="mt-1 text-foreground"
			>
				{updatedDate ?? "None"}
			</Typography>

			<Typography variant="bodySmall" className="text-muted-foreground mt-3">
				Tags
			</Typography>
			<div className="mt-1 flex flex-wrap">
				{taskRun.tags && taskRun.tags.length > 0 ? (
					taskRun.tags.map((tag) => <TagBadge key={tag} tag={tag} />)
				) : (
					<Typography
						variant="bodySmall"
						fontFamily="mono"
						className="text-foreground"
					>
						None
					</Typography>
				)}
			</div>
		</div>
	);
};
