import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import type { PaginationState } from "@tanstack/react-table";
import { useEffect, useState } from "react";
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
	const { data, isFetching, isPlaceholderData } = useQuery(
		buildPaginateGlobalConcurrencyLimitsQuery(filter),
	);

	useEffect(() => {
		if (!data || isFetching || isPlaceholderData) return;
		const lastPageIndex = Math.max(0, data.pages - 1);
		if (pagination.pageIndex > lastPageIndex) {
			onPaginationChange({ ...pagination, pageIndex: lastPageIndex });
		}
	}, [data, isFetching, isPlaceholderData, pagination, onPaginationChange]);

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
					data={data?.results ?? []}
					pageCount={data?.pages ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					searchValue={search}
					onSearchChange={onSearchChange}
					showFilteredEmptyState={data?.count === 0 && !isFetching}
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
