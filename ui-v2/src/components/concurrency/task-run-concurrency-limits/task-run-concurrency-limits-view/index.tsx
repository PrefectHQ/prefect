import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import type { PaginationState } from "@tanstack/react-table";
import { useEffect, useState } from "react";
import {
	buildCountTaskRunConcurrencyLimitsQuery,
	buildPaginateTaskRunConcurrencyLimitsQuery,
	buildTaskRunConcurrencyLimitsPaginationBody,
	type TaskRunConcurrencyLimit,
} from "@/api/task-run-concurrency-limits";

import { TaskRunConcurrencyLimitsDataTable } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-data-table";
import { TaskRunConcurrencyLimitsEmptyState } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-empty-state";
import { TaskRunConcurrencyLimitsHeader } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-header";
import {
	type DialogState,
	TaskRunConcurrencyLimitDialog,
} from "./task-run-concurrency-limit-dialog";

type TaskRunConcurrencyLimitsViewProps = {
	search: string | undefined;
	onSearchChange: (value: string) => void;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

export const TaskRunConcurrencyLimitsView = ({
	search,
	onSearchChange,
	pagination,
	onPaginationChange,
}: TaskRunConcurrencyLimitsViewProps) => {
	const [openDialog, setOpenDialog] = useState<DialogState>({
		dialog: null,
		data: undefined,
	});

	const filter = buildTaskRunConcurrencyLimitsPaginationBody({
		page: pagination.pageIndex + 1,
		limit: pagination.pageSize,
		search,
	});

	const { data: totalCount } = useSuspenseQuery(
		buildCountTaskRunConcurrencyLimitsQuery(),
	);
	const { data, isFetching, isPlaceholderData } = useQuery(
		buildPaginateTaskRunConcurrencyLimitsQuery(filter),
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
			{totalCount === 0 ? (
				<TaskRunConcurrencyLimitsEmptyState onAdd={handleAddRow} />
			) : (
				<TaskRunConcurrencyLimitsDataTable
					data={data?.results ?? []}
					pageCount={data?.pages ?? 0}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
					searchValue={search}
					onSearchChange={onSearchChange}
					showFilteredEmptyState={data?.count === 0 && !isFetching}
					onClearSearch={() => onSearchChange("")}
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
