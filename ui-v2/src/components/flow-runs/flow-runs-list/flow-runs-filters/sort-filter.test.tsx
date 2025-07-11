import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { SortFilter } from "./sort-filter";

describe("FlowRunsDataTable -- SortFilter", () => {
	beforeAll(mockPointerEvents);

	it("returns correct sort filter for Newest to oldest", async () => {
		// Setup
		const user = userEvent.setup();
		const mockOnSelectFn = vi.fn();
		render(<SortFilter value={undefined} onSelect={mockOnSelectFn} />);

		// Test
		await user.click(
			screen.getByRole("combobox", { name: /flow run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /newest to oldest/i }));

		// Assert
		expect(mockOnSelectFn).toBeCalledWith("START_TIME_DESC");
	});

	it("returns correct sort filter for Oldest to newest", async () => {
		// Setup
		const user = userEvent.setup();
		const mockOnSelectFn = vi.fn();
		render(<SortFilter value={undefined} onSelect={mockOnSelectFn} />);

		// Test
		await user.click(
			screen.getByRole("combobox", { name: /flow run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /oldest to newest/i }));

		// Assert
		expect(mockOnSelectFn).toBeCalledWith("START_TIME_ASC");
	});

	it("returns correct sort filter for A to Z", async () => {
		// Setup
		const user = userEvent.setup();
		const mockOnSelectFn = vi.fn();
		render(<SortFilter value={undefined} onSelect={mockOnSelectFn} />);

		// Test
		await user.click(
			screen.getByRole("combobox", { name: /flow run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /a to z/i }));

		// Assert
		expect(mockOnSelectFn).toBeCalledWith("NAME_ASC");
	});

	it("returns correct sort filter for Z to A", async () => {
		// Setup
		const user = userEvent.setup();
		const mockOnSelectFn = vi.fn();
		render(<SortFilter value={undefined} onSelect={mockOnSelectFn} />);

		// Test
		await user.click(
			screen.getByRole("combobox", { name: /flow run sort order/i }),
		);
		await user.click(screen.getByRole("option", { name: /z to a/i }));

		// Assert
		expect(mockOnSelectFn).toBeCalledWith("NAME_DESC");
	});
});
