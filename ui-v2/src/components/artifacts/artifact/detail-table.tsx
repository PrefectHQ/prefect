import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { DataTable } from "@/components/ui/data-table";
import { SearchInput } from "@/components/ui/input";

export type DetailTableProps = {
	tableData: string;
};

const columnHelper = createColumnHelper<Record<string, string>>();

export const DetailTable = ({ tableData }: DetailTableProps) => {
	const rows = useMemo(
		() => JSON.parse(tableData) as Record<string, string>[],
		[tableData],
	);
	const headers = useMemo(() => Object.keys(rows[0] ?? {}), [rows]);
	const [input, setInput] = useState<string>("");

	const columns = useMemo(
		() =>
			headers.map((header) =>
				columnHelper.display({
					id: header,
					header: () => header,
					cell: ({ row }) => {
						const value = String(row.original[header] ?? "");
						return (
							<span className="truncate block" title={value}>
								{value}
							</span>
						);
					},
				}),
			),
		[headers],
	);

	const filteredRows = useMemo(() => {
		if (!input) return rows;
		return rows.filter((row) =>
			Object.values(row).some((value) =>
				String(value).toLowerCase().includes(input.toLowerCase()),
			),
		);
	}, [input, rows]);

	const table = useReactTable({
		data: filteredRows,
		columns,
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		initialState: { pagination: { pageIndex: 0, pageSize: 10 } },
	});

	return (
		<div data-testid="table-display" className="mt-4">
			<div className="flex flex-row justify-end items-center mb-2">
				<SearchInput
					placeholder="Search"
					value={input}
					onChange={(e) => setInput(e.target.value)}
				/>
			</div>
			<DataTable table={table} />
		</div>
	);
};
