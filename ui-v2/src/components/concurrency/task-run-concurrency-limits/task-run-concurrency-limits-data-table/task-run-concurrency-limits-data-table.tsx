import { getRouteApi } from "@tanstack/react-router";
import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useDeferredValue, useMemo } from "react";
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

import { ActiveTaskRunCells } from "./active-task-runs-cell";
import { TagCell } from "./tag-cell";

const routeApi = getRouteApi("/concurrency-limits/");
const columnHelper = createColumnHelper<TaskRunConcurrencyLimit>();

const createColumns = ({
	onDeleteRow,
	onResetRow,
}: {
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
}) => [
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
];

type TaskRunConcurrencyLimitsDataTableProps = {
	data: Array<TaskRunConcurrencyLimit>;
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
};

export const TaskRunConcurrencyLimitsDataTable = ({
	data,
	onDeleteRow,
	onResetRow,
}: TaskRunConcurrencyLimitsDataTableProps) => {
	const navigate = routeApi.useNavigate();
	const { search } = routeApi.useSearch();
	const deferredSearch = useDeferredValue(search ?? "");

	const filteredData = useMemo(() => {
		return data.filter((row) =>
			row.tag.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const onClearSearch = () => {
		void navigate({
			to: ".",
			search: (prev) => ({ ...prev, search: "" }),
		});
	};

	return (
		<Table
			data={filteredData}
			onDeleteRow={onDeleteRow}
			onResetRow={onResetRow}
			searchValue={search}
			onSearchChange={(value) =>
				void navigate({
					to: ".",
					search: (prev) => ({ ...prev, search: value }),
				})
			}
			showFilteredEmptyState={data.length > 0 && filteredData.length === 0}
			onClearSearch={onClearSearch}
		/>
	);
};

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

type TableProps = {
	data: Array<TaskRunConcurrencyLimit>;
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
	onSearchChange: (value: string) => void;
	searchValue: string | undefined;
	showFilteredEmptyState: boolean;
	onClearSearch: () => void;
};

export function Table({
	data,
	onDeleteRow,
	onResetRow,
	onSearchChange,
	searchValue,
	showFilteredEmptyState,
	onClearSearch,
}: TableProps) {
	const table = useReactTable({
		data,
		columns: createColumns({ onDeleteRow, onResetRow }),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
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
