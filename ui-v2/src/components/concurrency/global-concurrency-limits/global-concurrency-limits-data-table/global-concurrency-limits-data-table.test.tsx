import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { Table } from "./global-concurrency-limits-data-table";

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
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
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

	it("calls onDelete upon clicking delete action menu item", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={mockFn}
				onEditRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));
		expect(mockFn).toBeCalledWith(MOCK_ROW);
	});
	it("calls onEdit upon clicking rest action menu item", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onEditRow={mockFn}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /edit/i }));
		expect(mockFn).toHaveBeenCalledWith(MOCK_ROW);
	});

	it("toggles active switch", async () => {
		const user = userEvent.setup();

		const { rerender } = render(
			<>
				<Toaster />
				<Table
					data={[MOCK_ROW]}
					onDeleteRow={vi.fn()}
					onEditRow={vi.fn()}
					searchValue=""
					onSearchChange={vi.fn()}
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
			<Table
				data={[{ ...MOCK_ROW, active: false }]}
				onDeleteRow={vi.fn()}
				onEditRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
		);

		expect(
			screen.getByRole("switch", { name: /toggle active/i }),
		).not.toBeChecked();
	});
});
