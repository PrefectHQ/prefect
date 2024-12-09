import { DataTable } from "@/components/ui/data-table";
import { type TaskRunConcurrencyLimit } from "@/hooks/task-run-concurrency-limits";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";

import { ActionsCell } from "./actions-cell";

const columnHelper = createColumnHelper<TaskRunConcurrencyLimit>();

const createColumns = ({
	onDeleteRow,
	onResetRow,
}: {
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
}) => [
	columnHelper.accessor("tag", {
		header: "Tag", // TODO: Make this a link when starting the tak run concurrency page
	}),
	columnHelper.accessor("concurrency_limit", {
		header: "Slots",
	}),
	columnHelper.accessor("active_slots", {
		header: "Active Task Runs", // TODO: Give this styling once knowing what it looks like
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => (
			<ActionsCell
				{...props}
				onDeleteRow={onDeleteRow}
				onResetRow={onResetRow}
			/>
		),
	}),
];

type Props = {
	data: Array<TaskRunConcurrencyLimit>;
	onDeleteRow: (row: TaskRunConcurrencyLimit) => void;
	onResetRow: (row: TaskRunConcurrencyLimit) => void;
};

export const TaskRunConcurrencyDataTable = ({
	data,
	onDeleteRow,
	onResetRow,
}: Props) => {
	const table = useReactTable({
		data,
		columns: createColumns({ onDeleteRow, onResetRow }),
		getCoreRowModel: getCoreRowModel(),
	});

	return <DataTable table={table} />;
};
