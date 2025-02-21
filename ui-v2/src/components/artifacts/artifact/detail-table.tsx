import { SearchInput } from "@/components/ui/input";
import {
	Table,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { useMemo, useState } from "react";

export type DetailTableProps = {
	tableData: string;
};

export const DetailTable = ({ tableData }: DetailTableProps) => {
	const table = JSON.parse(tableData) as Record<string, string>[];
	const headers = Object.keys(table[0]);
	const [input, setInput] = useState<string>("");

	const filteredTable = useMemo(() => {
		return table.filter((row) => {
			return Object.values(row).some((value: string) =>
				String(value).toLowerCase().includes(input.toLowerCase()),
			);
		});
	}, [input, table]);

	return (
		<div data-testid="table-display" className="mt-4">
			<div className="flex flex-row justify-end items-center mb-2">
				<div>
					<SearchInput
						placeholder="Search"
						value={input}
						onChange={(e) => setInput(e.target.value)}
					/>
				</div>
			</div>
			<div className="rounded-md border">
				<Table>
					<TableHeader className="bg-gray-100">
						{headers.map((header, index) => {
							return (
								<TableHead key={index} className="py-2 text-black">
									{header}
								</TableHead>
							);
						})}
					</TableHeader>
					{filteredTable.map((row, index) => {
						return (
							<TableRow key={index}>
								{headers.map((header, index) => {
									return <TableCell key={index}>{row[header]}</TableCell>;
								})}
							</TableRow>
						);
					})}
				</Table>
			</div>
		</div>
	);
};
