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
	const rows = JSON.parse(tableData) as Record<string, string>[];
	const headers = Object.keys(rows[0] ?? {});
	const [input, setInput] = useState<string>("");

	const columns = useMemo(
		() =>
			headers.map((header) =>
				columnHelper.accessor(header, {
					header,
					cell: ({ getValue }) => (
						<span
							className="truncate block max-w-[200px]"
							title={String(getValue() ?? "")}
						>
							{String(getValue() ?? "")}
						</span>
					),
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
