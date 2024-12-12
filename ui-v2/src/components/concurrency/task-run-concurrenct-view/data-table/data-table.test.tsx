import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Table } from "./data-table";

const MOCK_ROW = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [] as Array<string>,
};

describe("TaskRunDataTable -- table", () => {
	it("renders row data", () => {
		render(
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
		);
		expect(screen.getByRole("cell", { name: /my tag 0/i })).toBeVisible();
		expect(screen.getByRole("cell", { name: /1/i })).toBeVisible();
	});
	it("calls onDelete upon clicking delete action menu item", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={mockFn}
				onResetRow={vi.fn()}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));
		expect(mockFn).toHaveBeenCalledWith(MOCK_ROW);
	});
	it("calls onReset upon clicking rest action menu item", async () => {
		const user = userEvent.setup();
		const mockFn = vi.fn();

		render(
			<Table
				data={[MOCK_ROW]}
				onDeleteRow={vi.fn()}
				onResetRow={mockFn}
				searchValue=""
				onSearchChange={vi.fn()}
			/>,
		);
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /reset/i }));
		expect(mockFn).toHaveBeenCalledWith(MOCK_ROW);
	});
});
