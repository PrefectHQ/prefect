import { useSuspenseQueries } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsCountFilter,
	buildGlobalConcurrencyLimitsFilter,
	buildListGlobalConcurrencyLimitsQuery,
	type GlobalConcurrencyLimit,
} from "@/api/global-concurrency-limits";

import { GlobalConcurrencyLimitsDataTable } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-data-table";
import { GlobalConcurrencyLimitsEmptyState } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-empty-state";
import { GlobalConcurrencyLimitsHeader } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-header";

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

	const filter = useMemo(
		() => buildGlobalConcurrencyLimitsFilter(search),
		[search],
	);
	const countFilter = useMemo(
		() => buildGlobalConcurrencyLimitsCountFilter(search),
		[search],
	);

	const [{ data }, { data: filteredCount }, { data: totalCount }] =
		useSuspenseQueries({
			queries: [
				buildListGlobalConcurrencyLimitsQuery(filter),
				buildCountGlobalConcurrencyLimitsQuery(countFilter),
				buildCountGlobalConcurrencyLimitsQuery(),
			],
		});

	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex: search.offset ? Math.floor(search.offset / search.limit) : 0,
			pageSize: search.limit,
		}),
		[search.offset, search.limit],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					offset: newPagination.pageIndex * newPagination.pageSize,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onSearchChange = useCallback(
		(value: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					search: value || undefined,
					offset: 0,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onClearSearch = useCallback(() => onSearchChange(""), [onSearchChange]);

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

	const hasLimits = (totalCount ?? 0) > 0;
	const showFilteredEmptyState = hasLimits && (filteredCount ?? 0) === 0;

	return (
		<div className="flex flex-col gap-4">
			<GlobalConcurrencyLimitsHeader onAdd={handleAddRow} />
			{!hasLimits ? (
				<GlobalConcurrencyLimitsEmptyState onAdd={handleAddRow} />
			) : (
				<GlobalConcurrencyLimitsDataTable
					data={data}
					currentCount={filteredCount ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					onEditRow={handleEditRow}
					onDeleteRow={handleDeleteRow}
					onResetRow={handleResetRow}
					searchValue={search.search}
					onSearchChange={onSearchChange}
					showFilteredEmptyState={showFilteredEmptyState}
					onClearSearch={onClearSearch}
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
