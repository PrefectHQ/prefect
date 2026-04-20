import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "./data-table";

type TestData = { id: string; name: string };

const columnHelper = createColumnHelper<TestData>();
const columns = [
	columnHelper.accessor("name", {
		header: "Name",
		cell: (info) => info.getValue(),
	}),
];

const TestTable = ({
	data,
	onRowClick,
}: {
	data: TestData[];
	onRowClick?: (row: TestData) => void;
}) => {
	const table = useReactTable({
		data,
		columns,
		getCoreRowModel: getCoreRowModel(),
	});
	return <DataTable table={table} onRowClick={onRowClick} />;
};

describe("DataTable", () => {
	const testData: TestData[] = [
		{ id: "1", name: "Row 1" },
		{ id: "2", name: "Row 2" },
	];

	it("renders rows without cursor-pointer class when onRowClick is not provided", () => {
		render(<TestTable data={testData} />);

		const rows = screen.getAllByRole("row");
		// First row is the header, data rows start at index 1
		const dataRow = rows[1];
		expect(dataRow).not.toHaveClass("cursor-pointer");
	});

	it("renders rows with cursor-pointer and hover:bg-muted class when onRowClick is provided", () => {
		render(<TestTable data={testData} onRowClick={vi.fn()} />);

		const rows = screen.getAllByRole("row");
		const dataRow = rows[1];
		expect(dataRow).toHaveClass("cursor-pointer");
		expect(dataRow).toHaveClass("hover:bg-muted");
	});

	it("calls onRowClick with row data when a row is clicked", async () => {
		const onRowClick = vi.fn();
		render(<TestTable data={testData} onRowClick={onRowClick} />);

		await userEvent.click(screen.getByText("Row 1"));

		expect(onRowClick).toHaveBeenCalledOnce();
		expect(onRowClick).toHaveBeenCalledWith({ id: "1", name: "Row 1" });
	});

	it("does not call onRowClick when onRowClick is not provided and row is clicked", async () => {
		render(<TestTable data={testData} />);

		await userEvent.click(screen.getByText("Row 1"));
		// No error thrown, row is simply not clickable
		expect(screen.getByText("Row 1")).toBeInTheDocument();
	});
});
