import { TaskRunConcurrencyLimitActionsMenu } from "@/components/concurrency/_shared/task-run-concurrency-limit-actions-menu";
import { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";

import { NavHeader } from "./nav-header";

type Props = {
	data: TaskRunConcurrencyLimit;
	onDelete: () => void;
	onReset: () => void;
};

export const Header = ({ data, onDelete, onReset }: Props) => {
	return (
		<div className="flex items-center justify-between">
			<NavHeader tag={data.tag} />
			<TaskRunConcurrencyLimitActionsMenu
				id={data.id}
				onDelete={onDelete}
				onReset={onReset}
			/>
		</div>
	);
};
