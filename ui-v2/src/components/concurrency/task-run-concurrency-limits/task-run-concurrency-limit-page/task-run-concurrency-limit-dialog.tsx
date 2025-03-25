import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitsDeleteDialog } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-delete-dialog";
import { TaskRunConcurrencyLimitsResetDialog } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-reset-dialog";
import { getRouteApi } from "@tanstack/react-router";

export type Dialogs = null | "delete" | "reset";

const routeApi = getRouteApi("/concurrency-limits/");

type TaskRunConcurrencyLimitDialogProps = {
	data: TaskRunConcurrencyLimit;
	openDialog: Dialogs;
	onOpenChange: (open: boolean) => void;
	onCloseDialog: () => void;
};

export const TaskRunConcurrencyLimitDialog = ({
	data,
	openDialog,
	onCloseDialog,
	onOpenChange,
}: TaskRunConcurrencyLimitDialogProps) => {
	const navigate = routeApi.useNavigate();

	const handleDelete = () => {
		onCloseDialog();
		void navigate({ to: "/concurrency-limits", search: { tab: "task-run" } });
	};

	switch (openDialog) {
		case "reset":
			return (
				<TaskRunConcurrencyLimitsResetDialog
					data={data}
					onOpenChange={onOpenChange}
					onReset={onCloseDialog}
				/>
			);
		case "delete":
			return (
				<TaskRunConcurrencyLimitsDeleteDialog
					data={data}
					onOpenChange={onOpenChange}
					onDelete={handleDelete}
				/>
			);
		default:
			return null;
	}
};
