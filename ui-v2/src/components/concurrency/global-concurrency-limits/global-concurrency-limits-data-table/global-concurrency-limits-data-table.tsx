import type { OnChangeFn, PaginationState } from "@tanstack/react-table";
import { useCallback } from "react";
import type { GlobalConcurrencyLimit } from "@/api/global-concurrency-limits";
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
import { ActionsCell } from "./actions-cell";
import { ActiveCell } from "./active-cell";

const columnHelper = createColumnHelper<GlobalConcurrencyLimit>();

const createColumns = ({
	onEditRow,
	onDeleteRow,
	onResetRow,
}: {
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onResetRow: (row: GlobalConcurrencyLimit) => void;
}) =>
	columnHelper.columns([
		columnHelper.accessor("name", {
			header: "Name",
		}),
		columnHelper.accessor("limit", {
			header: "Limit",
		}),
		columnHelper.accessor("active_slots", {
			header: "Active Slots",
		}),
		columnHelper.accessor("slot_decay_per_second", {
			header: "Slots Decay Per Second",
		}),
		columnHelper.accessor("active", {
			header: "Active",
			cell: ActiveCell,
		}),
		columnHelper.display({
			id: "actions",
			cell: (props) => (
				<div className="flex flex-row justify-end">
					<ActionsCell
						{...props}
						onEditRow={onEditRow}
						onDeleteRow={onDeleteRow}
						onResetRow={onResetRow}
					/>
				</div>
			),
		}),
	]);

type GlobalConcurrencyLimitsDataTableProps = {
	data: Array<GlobalConcurrencyLimit>;
	currentCount: number;
	pagination: PaginationState;
	onPaginationChange: (newPagination: PaginationState) => void;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onResetRow: (row: GlobalConcurrencyLimit) => void;
	searchValue: string | undefined;
	onSearchChange: (value: string) => void;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export const GlobalConcurrencyLimitsDataTable = ({
	data,
	currentCount,
	pagination,
	onPaginationChange,
	onEditRow,
	onDeleteRow,
	onResetRow,
	searchValue,
	onSearchChange,
	showFilteredEmptyState,
	onClearSearch,
}: GlobalConcurrencyLimitsDataTableProps) => (
	<Table
		data={data}
		currentCount={currentCount}
		pagination={pagination}
		onPaginationChange={onPaginationChange}
		onDeleteRow={onDeleteRow}
		onEditRow={onEditRow}
		onResetRow={onResetRow}
		searchValue={searchValue}
		onSearchChange={onSearchChange}
		showFilteredEmptyState={showFilteredEmptyState}
		onClearSearch={onClearSearch}
	/>
);

const GlobalConcurrencyLimitsFilteredEmptyState = ({
	onClearSearch,
}: {
	onClearSearch: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>
			No global concurrency limits match your search
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

type TableProps = {
	data: Array<GlobalConcurrencyLimit>;
	currentCount: number;
	pagination: PaginationState;
	onPaginationChange: (newPagination: PaginationState) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onResetRow: (row: GlobalConcurrencyLimit) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export function Table({
	data,
	currentCount,
	pagination,
	onPaginationChange,
	onDeleteRow,
	onEditRow,
	onResetRow,
	onSearchChange,
	searchValue,
	showFilteredEmptyState,
	onClearSearch,
}: TableProps) {
	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			const newPagination =
				typeof updater === "function" ? updater(pagination) : updater;
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
	);

	const table = useTable({
		data,
		columns: createColumns({ onDeleteRow, onEditRow, onResetRow }),
		state: {
			pagination,
		},
		manualPagination: true,
		onPaginationChange: handlePaginationChange,
		rowCount: currentCount,
	});

	return (
		<div className="flex flex-col gap-4">
			<SearchInput
				className="max-w-72"
				placeholder="Search global concurrency limit"
				value={searchValue}
				onChange={(e) => onSearchChange(e.target.value)}
			/>
			{showFilteredEmptyState ? (
				<GlobalConcurrencyLimitsFilteredEmptyState
					onClearSearch={onClearSearch}
				/>
			) : (
				<DataTable table={table} />
			)}
		</div>
	);
}
