import { TaskRunConcurrencyLimitDeleteDialog } from "@/components/concurrency/_shared/task-run-concurrency-limit-delete-dialog";
import { TaskRunConcurrencyLimitResetDialog } from "@/components/concurrency/_shared/task-run-concurrency-limit-reset-dialog";
import { TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";

import { CreateLimitDialog } from "./create-dialog";

export type DialogState =
	| { dialog: null | "create"; data: undefined }
	| {
			dialog: "reset" | "delete";
			data: TaskRunConcurrencyLimit;
	  };

export const DialogView = ({
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
				<CreateLimitDialog
					onOpenChange={onOpenChange}
					onSubmit={onCloseDialog}
				/>
			);
		case "reset":
			return (
				<TaskRunConcurrencyLimitResetDialog
					data={data}
					onOpenChange={onOpenChange}
					onReset={onCloseDialog}
				/>
			);
		case "delete":
			return (
				<TaskRunConcurrencyLimitDeleteDialog
					data={data}
					onOpenChange={onOpenChange}
					onDelete={onCloseDialog}
				/>
			);
		default:
			return null;
	}
};
