import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitsActionsMenu } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-actions-menu";

import { NavHeader } from "./nav-header";

type TaskRunConcurrencyLimitHeaderProps = {
	data: TaskRunConcurrencyLimit;
	onDelete: () => void;
	onReset: () => void;
	canUpdate?: boolean;
	canDelete?: boolean;
};

export const TaskRunConcurrencyLimitHeader = ({
	data,
	onDelete,
	onReset,
	canUpdate,
	canDelete,
}: TaskRunConcurrencyLimitHeaderProps) => {
	return (
		<div className="flex items-center justify-between">
			<NavHeader tag={data.tag} />
			<TaskRunConcurrencyLimitsActionsMenu
				id={data.id}
				onDelete={onDelete}
				onReset={onReset}
				canUpdate={canUpdate}
				canDelete={canDelete}
			/>
		</div>
	);
};
