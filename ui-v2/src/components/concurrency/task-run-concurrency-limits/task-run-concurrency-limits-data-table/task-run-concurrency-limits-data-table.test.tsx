import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { TaskRunConcurrencyLimitsDataTable } from "./task-run-concurrency-limits-data-table";

const MOCK_ROW = createFakeTaskRunConcurrencyLimit({
	id: "0",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [],
});

type TableProps = React.ComponentProps<
	typeof TaskRunConcurrencyLimitsDataTable
>;

const DEFAULT_PROPS: TableProps = {
	data: [MOCK_ROW],
	onDeleteRow: vi.fn(),
	onResetRow: vi.fn(),
	pageCount: 1,
	pagination: { pageIndex: 0, pageSize: 10 },
	onPaginationChange: vi.fn(),
	onSearchChange: vi.fn(),
	searchValue: "",
	showFilteredEmptyState: false,
	onClearSearch: vi.fn(),
};

// Wraps the table in a router provider, because rows link to a limit's page
const renderTable = (props: Partial<TableProps> = {}) => {
	const rootRoute = createRootRoute({
		component: () => (
			<TaskRunConcurrencyLimitsDataTable {...DEFAULT_PROPS} {...props} />
		),
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return render(<RouterProvider router={router} />, {
		wrapper: createWrapper(),
	});
};

describe("TaskRunConcurrencyLimitsDataTable", () => {
	it("renders row data", async () => {
		renderTable();

		expect(await screen.findByText("my tag 0")).toBeVisible();
	});

	it("calls onPaginationChange upon paging through server-side pages", async () => {
		const user = userEvent.setup();
		const onPaginationChange = vi.fn();

		renderTable({ pageCount: 30, onPaginationChange });

		expect(await screen.findByText(/page 1 of 30/i)).toBeVisible();

		await user.click(screen.getByRole("button", { name: /go to next page/i }));
		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 1,
			pageSize: 10,
		});
	});

	it("calls onSearchChange upon typing in the search input", async () => {
		const user = userEvent.setup();
		const onSearchChange = vi.fn();

		renderTable({ onSearchChange });

		await user.type(
			await screen.findByPlaceholderText(/search active task limit/i),
			"a",
		);
		await waitFor(() => expect(onSearchChange).toHaveBeenCalledWith("a"));
	});

	it("renders the filtered empty state when nothing matches the search", async () => {
		const user = userEvent.setup();
		const onClearSearch = vi.fn();

		renderTable({
			data: [],
			pageCount: 0,
			searchValue: "nothing matches",
			showFilteredEmptyState: true,
			onClearSearch,
		});

		await user.click(
			await screen.findByRole("button", { name: /clear search/i }),
		);
		expect(onClearSearch).toHaveBeenCalled();
	});
});
