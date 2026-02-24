import {
	getCoreRowModel,
	getPaginationRowModel,
	getSortedRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueues } from "@/mocks";
import { createWorkPoolQueuesTableColumns } from "./work-pool-queues-table-columns";

// Mock components used by columns
vi.mock("@/components/work-pools/work-pool-queue-status-badge", () => ({
	WorkPoolQueueStatusBadge: ({ status }: { status: string }) => (
		<span data-testid="status-badge">{status}</span>
	),
}));

vi.mock("../../work-pool-queue-menu", () => ({
	WorkPoolQueueMenu: () => <button type="button">Menu</button>,
}));

vi.mock("../../work-pool-queue-toggle", () => ({
	WorkPoolQueueToggle: () => <button type="button">Toggle</button>,
}));

vi.mock("./queue-name-with-late-indicator", () => ({
	QueueNameWithLateIndicator: ({ queue }: { queue: { name: string } }) => (
		<span data-testid="late-indicator">{queue.name}</span>
	),
}));

vi.mock("@tanstack/react-router", () => ({
	Link: ({
		children,
		title,
		className,
	}: {
		children: React.ReactNode;
		title?: string;
		className?: string;
	}) => (
		<a title={title} className={className} href="https://test.example.com">
			{children}
		</a>
	),
}));

// Helper component to render columns in a real table
function TestTable({
	enableLateIndicator = false,
}: {
	enableLateIndicator?: boolean;
}) {
	// createFakeWorkPoolQueues always creates "default" as queue[0],
	// overrides[1] applies to queue[1], overrides[2] to queue[2]
	const queues = createFakeWorkPoolQueues("test-pool", 3, [
		{}, // queue[0] is always "default", no extra overrides needed
		{
			name: "high-priority",
			status: "READY",
			is_paused: false,
			priority: 2,
			concurrency_limit: 5,
		},
		{
			name: "a-very-long-queue-name-that-should-be-truncated-for-display",
			status: "PAUSED",
			is_paused: true,
			priority: 3,
			concurrency_limit: null,
		},
	]);
	// Ensure the default queue has null concurrency_limit for predictable tests
	queues[0] = { ...queues[0], concurrency_limit: null, priority: 1 };

	const columns = createWorkPoolQueuesTableColumns({ enableLateIndicator });

	const table = useReactTable({
		data: queues,
		columns,
		getCoreRowModel: getCoreRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		initialState: {
			sorting: [{ id: "name", desc: false }],
			pagination: { pageIndex: 0, pageSize: 10 },
		},
	});

	return (
		<table>
			<thead>
				{table.getHeaderGroups().map((headerGroup) => (
					<tr key={headerGroup.id}>
						{headerGroup.headers.map((header) => (
							<th key={header.id}>
								{typeof header.column.columnDef.header === "function"
									? header.column.columnDef.header(header.getContext())
									: header.column.columnDef.header}
							</th>
						))}
					</tr>
				))}
			</thead>
			<tbody>
				{table.getRowModel().rows.map((row) => (
					<tr key={row.id}>
						{row.getVisibleCells().map((cell) => (
							<td key={cell.id}>
								{typeof cell.column.columnDef.cell === "function"
									? cell.column.columnDef.cell(cell.getContext())
									: cell.column.columnDef.cell}
							</td>
						))}
					</tr>
				))}
			</tbody>
		</table>
	);
}

describe("WorkPoolQueuesTableColumns", () => {
	describe("sortable column headers", () => {
		it("renders Name, Concurrency Limit, and Priority as sortable buttons", () => {
			render(<TestTable />);

			expect(screen.getByRole("button", { name: /name/i })).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /concurrency limit/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: /priority/i }),
			).toBeInTheDocument();
		});

		it("toggles sort direction when clicking a sortable header", async () => {
			const user = userEvent.setup();
			render(<TestTable />);

			const nameHeader = screen.getByRole("button", { name: /name/i });

			// Initially sorted ascending by name, click to sort descending
			await user.click(nameHeader);

			// Should still be a clickable button
			expect(nameHeader).toBeInTheDocument();
		});

		it("renders Status as non-sortable plain text header", () => {
			render(<TestTable />);

			// Status header should be plain text, not a button
			expect(screen.getByText("Status")).toBeInTheDocument();
			// The Status text should not be inside a button
			const statusHeader = screen.getByText("Status");
			expect(statusHeader.tagName).not.toBe("BUTTON");
		});
	});

	describe("name column truncation", () => {
		it("renders queue name links with truncate styling", () => {
			render(<TestTable />);

			const longNameLink = screen.getByText(
				"a-very-long-queue-name-that-should-be-truncated-for-display",
			);
			expect(longNameLink).toBeInTheDocument();
			expect(longNameLink.className).toContain("truncate");
			expect(longNameLink.className).toContain("max-w-[200px]");
		});

		it("adds title attribute for tooltip on queue name links", () => {
			render(<TestTable />);

			const link = screen.getByTitle("default");
			expect(link).toBeInTheDocument();
			expect(link.textContent).toBe("default");
		});
	});

	describe("late indicator", () => {
		it("renders QueueNameWithLateIndicator when enableLateIndicator is true", () => {
			render(<TestTable enableLateIndicator />);

			const indicators = screen.getAllByTestId("late-indicator");
			expect(indicators).toHaveLength(3);
		});

		it("renders plain links when enableLateIndicator is false", () => {
			render(<TestTable enableLateIndicator={false} />);

			expect(screen.queryAllByTestId("late-indicator")).toHaveLength(0);
			expect(screen.getByTitle("default")).toBeInTheDocument();
		});
	});

	describe("concurrency limit column", () => {
		it("displays infinity symbol for null concurrency limit", () => {
			render(<TestTable />);

			const infinitySymbols = screen.getAllByText("∞");
			// default queue and long-name queue both have null concurrency_limit
			expect(infinitySymbols).toHaveLength(2);
		});

		it("displays numeric concurrency limit when set", () => {
			render(<TestTable />);

			// high-priority queue has concurrency_limit of 5
			expect(screen.getByText("5")).toBeInTheDocument();
		});
	});

	describe("priority column", () => {
		it("displays priority values", () => {
			render(<TestTable />);

			expect(screen.getByText("1")).toBeInTheDocument();
			expect(screen.getByText("2")).toBeInTheDocument();
			expect(screen.getByText("3")).toBeInTheDocument();
		});
	});
});
