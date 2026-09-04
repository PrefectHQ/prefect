import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import type { PaginationState } from "@tanstack/react-table";
import { useState } from "react";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsPaginationBody,
	buildPaginateGlobalConcurrencyLimitsQuery,
	type GlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";

import { GlobalConcurrencyLimitsDataTable } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-data-table";
import { GlobalConcurrencyLimitsEmptyState } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-empty-state";
import { GlobalConcurrencyLimitsHeader } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-header";

import {
	type DialogState,
	GlobalConcurrencyLimitsDialog,
} from "./global-conccurency-limits-dialog";

type GlobalConcurrencyLimitsViewProps = {
	search: string | undefined;
	onSearchChange: (value: string) => void;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

export const GlobalConcurrencyLimitsView = ({
	search,
	onSearchChange,
	pagination,
	onPaginationChange,
}: GlobalConcurrencyLimitsViewProps) => {
	const [openDialog, setOpenDialog] = useState<DialogState>({
		dialog: null,
		data: undefined,
	});

	const filter = buildGlobalConcurrencyLimitsPaginationBody({
		page: pagination.pageIndex + 1,
		limit: pagination.pageSize,
		search,
	});

	const { data: totalCount } = useSuspenseQuery(
		buildCountGlobalConcurrencyLimitsQuery(),
	);
	const { data, isPending } = useQuery(
		buildPaginateGlobalConcurrencyLimitsQuery(filter),
	);
	const { data: filteredCount = 0 } = useQuery(
		buildCountGlobalConcurrencyLimitsQuery({
			concurrency_limits: filter.concurrency_limits,
		}),
	);

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
			<GlobalConcurrencyLimitsHeader onAdd={handleAddRow} />
			{totalCount === 0 ? (
				<GlobalConcurrencyLimitsEmptyState onAdd={handleAddRow} />
			) : (
				<GlobalConcurrencyLimitsDataTable
					data={data ?? []}
					pageCount={Math.ceil(filteredCount / pagination.pageSize)}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					searchValue={search}
					onSearchChange={onSearchChange}
					showFilteredEmptyState={filteredCount === 0 && !isPending}
					onClearSearch={() => onSearchChange("")}
					onEditRow={handleEditRow}
					onDeleteRow={handleDeleteRow}
					onResetRow={handleResetRow}
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
