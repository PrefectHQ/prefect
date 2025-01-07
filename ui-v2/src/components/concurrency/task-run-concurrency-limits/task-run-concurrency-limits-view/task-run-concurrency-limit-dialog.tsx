import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitsCreateDialog } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-create-dialog";
import { TaskRunConcurrencyLimitsDeleteDialog } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-delete-dialog";
import { TaskRunConcurrencyLimitsResetDialog } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-reset-dialog";

export type DialogState =
	| { dialog: null | "create"; data: undefined }
	| {
			dialog: "reset" | "delete";
			data: TaskRunConcurrencyLimit;
	  };

export const TaskRunConcurrencyLimitDialog = ({
	openDialog,
	onCloseDialog,
	onOpenChange,
}: {
	openDialog: DialogState;
	onOpenChange: (open: boolean) => void;
	onCloseDialog: () => void;
}) => {
	const { dialog, data } = openDialog;
	switch (dialog) {
		case "create":
			return (
				<TaskRunConcurrencyLimitsCreateDialog
					onOpenChange={onOpenChange}
					onSubmit={onCloseDialog}
				/>
			);
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
					onDelete={onCloseDialog}
				/>
			);
		default:
			return null;
	}
};
