import type { OnChangeFn, PaginationState } from "@tanstack/react-table";
import { useCallback } from "react";
import type { TaskRunConcurrencyLimit } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitsActionsMenu } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-actions-menu";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { SearchInput } from "@/components/ui/input";
import { createColumnHelper, useTable } from "@/lib/tanstack-table";

import { ActiveTaskRunCells } from "./active-task-runs-cell";
import { TagCell } from "./tag-cell";

const columnHelper = createColumnHelper<TaskRunConcurrencyLimit>();

const createColumns = ({
	onDeleteRow,
	onResetRow,
}: {
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
}) =>
	columnHelper.columns([
		columnHelper.accessor("tag", {
			header: "Tag",
			cell: TagCell,
		}),
		columnHelper.accessor("concurrency_limit", {
			header: "Slots",
		}),
		columnHelper.accessor("active_slots", {
			header: "Active Task Runs",
			cell: ActiveTaskRunCells,
		}),
		columnHelper.display({
			id: "actions",
			cell: (props) => {
				const row = props.row.original;
				return (
					<div className="flex flex-row justify-end">
						<TaskRunConcurrencyLimitsActionsMenu
							id={row.id}
							onDelete={() => onDeleteRow(row)}
							onReset={() => onResetRow(row)}
						/>
					</div>
				);
			},
		}),
	]);

const TaskRunConcurrencyLimitsFilteredEmptyState = ({
	onClearSearch,
}: {
	onClearSearch: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>
			No task-run concurrency limits match your search
		</EmptyStateTitle>
		<EmptyStateDescription>
			Try adjusting your search terms.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button variant="outline" onClick={onClearSearch}>
				Clear search
			</Button>
		</EmptyStateActions>
	</EmptyState>
);

type TaskRunConcurrencyLimitsDataTableProps = {
	data: Array<TaskRunConcurrencyLimit>;
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
	pageCount: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export function TaskRunConcurrencyLimitsDataTable({
	data,
	onDeleteRow,
	onResetRow,
	pageCount,
	pagination,
	onPaginationChange,
	onSearchChange,
	searchValue,
	showFilteredEmptyState,
	onClearSearch,
}: TaskRunConcurrencyLimitsDataTableProps) {
	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			onPaginationChange(
				typeof updater === "function" ? updater(pagination) : updater,
			);
		},
		[pagination, onPaginationChange],
	);

	const table = useTable({
		data,
		columns: createColumns({ onDeleteRow, onResetRow }),
		pageCount,
		manualPagination: true,
		state: { pagination },
		onPaginationChange: handlePaginationChange,
	});

	return (
		<div className="flex flex-col gap-4">
			<SearchInput
				className="max-w-72"
				placeholder="Search active task limit"
				value={searchValue}
				onChange={(e) => onSearchChange(e.target.value)}
			/>
			{showFilteredEmptyState ? (
				<TaskRunConcurrencyLimitsFilteredEmptyState
					onClearSearch={onClearSearch}
				/>
			) : (
				<DataTable table={table} />
			)}
		</div>
	);
}
