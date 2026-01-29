import { useMemo } from "react";
import type { TaskRun } from "@/api/task-runs";
import { KeyValue } from "@/components/ui/key-value";
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

			<div className="mt-3 flex flex-col gap-3">
				<KeyValue
					label="Created"
					value={<span className="font-mono">{createdDate ?? "None"}</span>}
				/>

				<KeyValue
					label="Last Updated"
					value={<span className="font-mono">{updatedDate ?? "None"}</span>}
				/>

				<KeyValue
					label="Tags"
					value={
						taskRun.tags && taskRun.tags.length > 0 ? (
							<div className="flex flex-wrap">
								{taskRun.tags.map((tag) => (
									<TagBadge key={tag} tag={tag} />
								))}
							</div>
						) : (
							<span className="font-mono">None</span>
						)
					}
				/>
			</div>
		</div>
	);
};
