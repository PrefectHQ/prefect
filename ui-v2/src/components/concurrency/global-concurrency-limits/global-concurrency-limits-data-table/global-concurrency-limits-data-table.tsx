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

type GlobalConcurrencyLimitsDataTableProps = {
	data: Array<GlobalConcurrencyLimit>;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onResetRow: (row: GlobalConcurrencyLimit) => void;
	pageCount: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export function GlobalConcurrencyLimitsDataTable({
	data,
	onDeleteRow,
	onEditRow,
	onResetRow,
	pageCount,
	pagination,
	onPaginationChange,
	onSearchChange,
	searchValue,
	showFilteredEmptyState,
	onClearSearch,
}: GlobalConcurrencyLimitsDataTableProps) {
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
		columns: createColumns({ onDeleteRow, onEditRow, onResetRow }),
		pageCount,
		manualPagination: true,
		state: { pagination },
		onPaginationChange: handlePaginationChange,
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
