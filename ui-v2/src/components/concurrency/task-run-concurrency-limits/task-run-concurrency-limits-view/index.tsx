import { useState } from "react";
import {
	type TaskRunConcurrencyLimit,
	useListTaskRunConcurrencyLimits,
} from "@/api/task-run-concurrency-limits";

import { TaskRunConcurrencyLimitsDataTable } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-data-table";
import { TaskRunConcurrencyLimitsEmptyState } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-empty-state";
import { TaskRunConcurrencyLimitsHeader } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-header";
import {
	type DialogState,
	TaskRunConcurrencyLimitDialog,
} from "./task-run-concurrency-limit-dialog";

export const TaskRunConcurrencyLimitsView = () => {
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
		<div className="flex flex-col gap-4">
			<TaskRunConcurrencyLimitsHeader onAdd={handleAddRow} />
			{data.length === 0 ? (
				<TaskRunConcurrencyLimitsEmptyState onAdd={handleAddRow} />
			) : (
				<TaskRunConcurrencyLimitsDataTable
					data={data}
					onDeleteRow={handleDeleteRow}
					onResetRow={handleResetRow}
				/>
			)}
			<TaskRunConcurrencyLimitDialog
				openDialog={openDialog}
				onCloseDialog={handleCloseDialog}
				onOpenChange={handleOpenChange}
			/>
		</div>
	);
};
