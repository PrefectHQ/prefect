import {
	type GlobalConcurrencyLimit,
	useListGlobalConcurrencyLimits,
} from "@/hooks/global-concurrency-limits";
import { useState } from "react";

import { GlobalConcurrencyDataTable } from "./data-table";
import { type DialogState, DialogView } from "./dialog";
import { GlobalConcurrencyLimitEmptyState } from "./empty-state";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

export const GlobalConcurrencyView = () => {
	const [openDialog, setOpenDialog] = useState<DialogState>({
		dialog: null,
		data: undefined,
	});

	const { data } = useListGlobalConcurrencyLimits();

	const handleAddRow = () =>
		setOpenDialog({ dialog: "create", data: undefined });

	const handleEditRow = (data: GlobalConcurrencyLimit) =>
		setOpenDialog({ dialog: "edit", data });

	const handleDeleteRow = (data: GlobalConcurrencyLimit) =>
		setOpenDialog({ dialog: "delete", data });

	const handleResetRow = (data: GlobalConcurrencyLimit) =>
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
			{data.length === 0 ? (
				<GlobalConcurrencyLimitEmptyState onAdd={handleAddRow} />
			) : (
				<div className="flex flex-col gap-4">
					<GlobalConcurrencyLimitsHeader onAdd={handleAddRow} />
					<GlobalConcurrencyDataTable
						data={data}
						onEditRow={handleEditRow}
						onDeleteRow={handleDeleteRow}
						onResetRow={handleResetRow}
					/>
				</div>
			)}
			<DialogView
				openDialog={openDialog}
				onCloseDialog={handleCloseDialog}
				onOpenChange={handleOpenChange}
			/>
		</>
	);
};
