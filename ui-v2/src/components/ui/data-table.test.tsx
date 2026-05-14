import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "./data-table";

type TestData = { id: string; name: string };

const columnHelper = createColumnHelper<TestData>();
const columns = [
	columnHelper.accessor("name", {
		header: "Name",
		cell: (info) => (
			<>
				<span>{info.getValue()}</span>
				<button type="button">Row action {info.row.original.id}</button>
			</>
		),
	}),
];

const resizableColumns = [
	columnHelper.accessor("name", {
		id: "name",
		header: "Name",
		cell: (info) => <span>{info.getValue()}</span>,
		size: 200,
		minSize: 50,
	}),
	columnHelper.display({
		id: "actions",
		cell: () => <span>actions</span>,
		enableResizing: false,
		size: 60,
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

const ResizableTestTable = ({ data }: { data: TestData[] }) => {
	const table = useReactTable({
		data,
		columns: resizableColumns,
		getCoreRowModel: getCoreRowModel(),
		enableColumnResizing: true,
		columnResizeMode: "onChange",
	});
	return <DataTable table={table} />;
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

	it("does not call onRowClick when a row action is clicked", async () => {
		const onRowClick = vi.fn();
		render(<TestTable data={testData} onRowClick={onRowClick} />);

		await userEvent.click(screen.getByRole("button", { name: "Row action 1" }));

		expect(onRowClick).not.toHaveBeenCalled();
	});

	it("does not call onRowClick when onRowClick is not provided and row is clicked", async () => {
		render(<TestTable data={testData} />);

		await userEvent.click(screen.getByText("Row 1"));
		// No error thrown, row is simply not clickable
		expect(screen.getByText("Row 1")).toBeInTheDocument();
	});

	describe("column resizing", () => {
		it("renders a resize handle for resizable columns and omits it for non-resizable columns", () => {
			render(<ResizableTestTable data={testData} />);

			expect(
				screen.getByTestId("column-resize-handle-name"),
			).toBeInTheDocument();
			expect(
				screen.queryByTestId("column-resize-handle-actions"),
			).not.toBeInTheDocument();
		});

		it("does not render resize handles when resizing is not enabled on the table", () => {
			render(<TestTable data={testData} />);

			expect(
				screen.queryByTestId(/column-resize-handle/),
			).not.toBeInTheDocument();
		});

		it("resizes the column when the handle is dragged", () => {
			render(<ResizableTestTable data={testData} />);

			const nameHeader = screen.getByRole("columnheader", { name: "Name" });
			expect(nameHeader).toHaveStyle({ width: "200px" });

			const handle = screen.getByTestId("column-resize-handle-name");

			fireEvent.mouseDown(handle, { clientX: 200 });
			fireEvent.mouseMove(document, { clientX: 280 });
			fireEvent.mouseUp(document, { clientX: 280 });

			expect(nameHeader).toHaveStyle({ width: "280px" });
		});

		it("resets the column width when the handle is double-clicked", () => {
			render(<ResizableTestTable data={testData} />);

			const nameHeader = screen.getByRole("columnheader", { name: "Name" });
			const handle = screen.getByTestId("column-resize-handle-name");

			fireEvent.mouseDown(handle, { clientX: 200 });
			fireEvent.mouseMove(document, { clientX: 320 });
			fireEvent.mouseUp(document, { clientX: 320 });
			expect(nameHeader).toHaveStyle({ width: "320px" });

			fireEvent.doubleClick(handle);
			expect(nameHeader).toHaveStyle({ width: "200px" });
		});
	});
});
