import { useMemo, useState } from "react";
import { SearchInput } from "@/components/ui/input";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

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
						<TableRow>
							{headers.map((header) => {
								return (
									<TableHead key={header} className="py-2 text-black">
										{header}
									</TableHead>
								);
							})}
						</TableRow>
					</TableHeader>
					<TableBody>
						{filteredTable.map((row) => {
							return (
								<TableRow key={row.id}>
									{headers.map((header) => {
										return <TableCell key={header}>{row[header]}</TableCell>;
									})}
								</TableRow>
							);
						})}
					</TableBody>
				</Table>
			</div>
		</div>
	);
};
