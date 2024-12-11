import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { Table } from "./data-table";

const MOCK_DATA = [
	{
		id: "0",
		created: "2021-01-01T00:00:00Z",
		updated: "2021-01-01T00:00:00Z",
		active: true,
		name: "global concurrency limit 0",
		limit: 0,
		active_slots: 0,
		slot_decay_per_second: 0,
	},
];

describe("GlobalConcurrencyLimitTable -- table", () => {
	it("renders row data", () => {
		render(
			<Table
				data={MOCK_DATA}
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
				data={MOCK_DATA}
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
		expect(mockFn).toHaveBeenCalledOnce();
	});
	it("calls onEdit upon clicking rest action menu item", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<Table
				data={MOCK_DATA}
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
		expect(mockFn).toHaveBeenCalledOnce();
	});
});
