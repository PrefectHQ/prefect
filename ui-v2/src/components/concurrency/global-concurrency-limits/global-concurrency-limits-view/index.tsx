import { useState } from "react";
import {
	type GlobalConcurrencyLimit,
	useListGlobalConcurrencyLimits,
} from "@/api/global-concurrency-limits";

import { GlobalConcurrencyLimitsDataTable } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-data-table";
import { GlobalConcurrencyLimitsEmptyState } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-empty-state";
import { GlobalConcurrencyLimitsHeader } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-header";

import {
	type DialogState,
	GlobalConcurrencyLimitsDialog,
} from "./global-conccurency-limits-dialog";

type GlobalConcurrencyLimitsViewProps = {
	canCreate?: boolean;
	canUpdate?: boolean;
	canDelete?: boolean;
};

export const GlobalConcurrencyLimitsView = ({
	canCreate,
	canUpdate,
	canDelete,
}: GlobalConcurrencyLimitsViewProps = {}) => {
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
		<div className="flex flex-col gap-4">
			<GlobalConcurrencyLimitsHeader
				onAdd={handleAddRow}
				canCreate={canCreate}
			/>
			{data.length === 0 ? (
				<GlobalConcurrencyLimitsEmptyState
					onAdd={handleAddRow}
					canCreate={canCreate}
				/>
			) : (
				<GlobalConcurrencyLimitsDataTable
					data={data}
					onEditRow={handleEditRow}
					onDeleteRow={handleDeleteRow}
					onResetRow={handleResetRow}
					canUpdate={canUpdate}
					canDelete={canDelete}
				/>
			)}
			<GlobalConcurrencyLimitsDialog
				openDialog={openDialog}
				onCloseDialog={handleCloseDialog}
				onOpenChange={handleOpenChange}
			/>
		</div>
	);
};
