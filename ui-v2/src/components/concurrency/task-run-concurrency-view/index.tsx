import {
	TaskRunConcurrencyLimit,
	useListTaskRunConcurrencyLimits,
} from "@/hooks/task-run-concurrency-limits";
import { useState } from "react";
import { TaskRunConcurrencyDataTable } from "./data-table";
import { DialogState, DialogView } from "./dialogs";
import { TaskRunConcurrencyLimitEmptyState } from "./empty-state";
import { TaskRunConcurrencyLimitsHeader } from "./header";

export const TaskRunConcurrencyView = () => {
	const [openDialog, setOpenDialog] = useState<DialogState>({
		dialog: null,
		data: undefined,
	});

	const { data } = useListTaskRunConcurrencyLimits();

	const handleAddRow = () =>
		setOpenDialog({ dialog: "create", data: undefined });

	const handleDeleteRow = (data: TaskRunConcurrencyLimit) =>
		setOpenDialog({ dialog: "delete", data });

	const handleResetRow = (data: TaskRunConcurrencyLimit) =>
		setOpenDialog({ dialog: "reset", data });

	const handleCloseDialog = () =>
		setOpenDialog({ dialog: null, data: undefined });

	// Because all modals will be rendered, only control the closing logic
	const handleOpenChange = (open: boolean) => {
		if (!open) {
			handleCloseDialog();
		}
	};

	return (
		<>
			<div className="flex flex-col gap-4">
				<TaskRunConcurrencyLimitsHeader onAdd={handleAddRow} />
				{data.length === 0 ? (
					<TaskRunConcurrencyLimitEmptyState onAdd={handleAddRow} />
				) : (
					<TaskRunConcurrencyDataTable
						data={data}
						onDeleteRow={handleDeleteRow}
						onResetRow={handleResetRow}
					/>
				)}
				<DialogView
					openDialog={openDialog}
					onCloseDialog={handleCloseDialog}
					onOpenChange={handleOpenChange}
				/>
			</div>
		</>
	);
};
