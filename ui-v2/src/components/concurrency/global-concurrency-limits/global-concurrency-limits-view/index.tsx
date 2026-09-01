import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsPaginationBody,
	buildPaginateGlobalConcurrencyLimitsQuery,
	type GlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";

import { GlobalConcurrencyLimitsDataTable } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-data-table";
import { GlobalConcurrencyLimitsEmptyState } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-empty-state";
import { GlobalConcurrencyLimitsHeader } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-header";
import { usePageSizePreference } from "@/hooks/use-page-size-preference";

import {
	type DialogState,
	GlobalConcurrencyLimitsDialog,
} from "./global-conccurency-limits-dialog";

const routeApi = getRouteApi("/concurrency-limits/");

export const GlobalConcurrencyLimitsView = () => {
	const [openDialog, setOpenDialog] = useState<DialogState>({
		dialog: null,
		data: undefined,
	});

	const search = routeApi.useSearch();
	const navigate = routeApi.useNavigate();
	const [pagination, onPaginationChange] = usePagination();

	const filter = buildGlobalConcurrencyLimitsPaginationBody({
		page: pagination.pageIndex + 1,
		limit: pagination.pageSize,
		search: search.search,
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

	const onSearchChange = (value: string) =>
		void navigate({
			to: ".",
			search: (prev) => ({ ...prev, search: value, page: 1 }),
			replace: true,
		});

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
					searchValue={search.search}
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

/**
 * Keeps the table's pagination state in the URL.
 *
 * React Table uses 0-based page indexes, the URL uses 1-based page numbers.
 */
const usePagination = () => {
	const search = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onInitializePageSize = useCallback(
		(pageSize: number) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, limit: pageSize }),
				replace: true,
			});
		},
		[navigate],
	);

	const pageSize = usePageSizePreference(search.limit, onInitializePageSize);
	const pageIndex = search.page - 1;

	const pagination: PaginationState = useMemo(
		() => ({ pageIndex, pageSize }),
		[pageIndex, pageSize],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};
