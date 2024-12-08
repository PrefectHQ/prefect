import { DataTable } from "@/components/ui/data-table";
import { type GlobalConcurrencyLimit } from "@/hooks/global-concurrency-limits";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";

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
}) => [
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
			<ActionsCell
				{...props}
				onEditRow={onEditRow}
				onDeleteRow={onDeleteRow}
				onResetRow={onResetRow}
			/>
		),
	}),
];

type Props = {
	data: Array<GlobalConcurrencyLimit>;
	onEditRow: (row: GlobalConcurrencyLimit) => void;
	onDeleteRow: (row: GlobalConcurrencyLimit) => void;
	onResetRow: (row: GlobalConcurrencyLimit) => void;
};

export const GlobalConcurrencyDataTable = ({
	data,
	onEditRow,
	onDeleteRow,
	onResetRow,
}: Props) => {
	const table = useReactTable({
		data,
		columns: createColumns({ onEditRow, onDeleteRow, onResetRow }),
		getCoreRowModel: getCoreRowModel(),
	});

	return <DataTable table={table} />;
};
