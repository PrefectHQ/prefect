import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { GlobalConcurrencyLimitsDataTable } from "./global-concurrency-limits-data-table";

const MOCK_ROW = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	active: true,
	name: "global concurrency limit 0",
	limit: 0,
	active_slots: 0,
	slot_decay_per_second: 0,
};

describe("GlobalConcurrencyLimitTable -- table", () => {
	it("renders row data", () => {
		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		expect(
			screen.getByRole("cell", { name: /global concurrency limit 0/i }),
		).toBeVisible();
		expect(
			screen.getByRole("switch", { name: /toggle active/i }),
		).toBeChecked();
	});

	it("calls onPaginationChange upon paging through server-side pages", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={30}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={mockFn}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText(/page 1 of 30/i)).toBeVisible();

		await user.click(screen.getByRole("button", { name: /go to next page/i }));
		expect(mockFn).toHaveBeenCalledWith({ pageIndex: 1, pageSize: 10 });
	});

	it("calls onSearchChange upon typing in the search input", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={mockFn}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.type(
			screen.getByPlaceholderText(/search global concurrency limit/i),
			"a",
		);
		await waitFor(() => expect(mockFn).toHaveBeenCalledWith("a"));
	});

	it("renders the filtered empty state when nothing matches the search", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue="nothing matches"
				onSearchChange={vi.fn()}
				showFilteredEmptyState
				onClearSearch={mockFn}
				pageCount={0}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: /clear search/i }));
		expect(mockFn).toHaveBeenCalled();
	});

	it("calls onDelete upon clicking delete action menu item", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={mockFn}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));
		expect(mockFn).toBeCalledWith(MOCK_ROW);
	});
	it("calls onEdit upon clicking edit action menu item", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={mockFn}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /edit/i }));
		expect(mockFn).toHaveBeenCalledWith(MOCK_ROW);
	});

	it("calls onReset upon clicking reset action menu item", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<GlobalConcurrencyLimitsDataTable
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={mockFn}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /reset/i }));
		expect(mockFn).toHaveBeenCalledWith(MOCK_ROW);
	});

	it("toggles active switch", async () => {
		const user = userEvent.setup();

		const { rerender } = render(
			<>
				<Toaster />
				<GlobalConcurrencyLimitsDataTable
					data={[MOCK_ROW]}
					onDeleteRow={vi.fn()}
					onEditRow={vi.fn()}
					onResetRow={vi.fn()}
					searchValue=""
					onSearchChange={vi.fn()}
					showFilteredEmptyState={false}
					onClearSearch={vi.fn()}
					pageCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);
		expect(
			screen.getByRole("switch", { name: /toggle active/i }),
		).toBeChecked();

		await user.click(
			screen.getByRole("switch", {
				name: /toggle active/i,
			}),
		);

		await waitFor(() => {
			expect(screen.getByText("Concurrency limit updated")).toBeVisible();
		});

		rerender(
			<GlobalConcurrencyLimitsDataTable
				data={[{ ...MOCK_ROW, active: false }]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
				showFilteredEmptyState={false}
				onClearSearch={vi.fn()}
				pageCount={1}
				pagination={{ pageIndex: 0, pageSize: 10 }}
				onPaginationChange={vi.fn()}
			/>,
		);

		expect(
			screen.getByRole("switch", { name: /toggle active/i }),
		).not.toBeChecked();
	});
});
