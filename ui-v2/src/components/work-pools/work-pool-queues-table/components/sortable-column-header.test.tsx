import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SortableColumnHeader } from "./sortable-column-header";

const createMockColumn = (isSorted: false | "asc" | "desc" = false) => ({
	getIsSorted: vi.fn().mockReturnValue(isSorted),
	toggleSorting: vi.fn(),
});

describe("SortableColumnHeader", () => {
	it("renders the label text", () => {
		const column = createMockColumn();
		render(
			<SortableColumnHeader column={column as never} label="Test Column" />,
		);

		expect(
			screen.getByRole("button", { name: /test column/i }),
		).toBeInTheDocument();
	});

	it("calls toggleSorting with true when currently sorted ascending", async () => {
		const user = userEvent.setup();
		const column = createMockColumn("asc");
		render(<SortableColumnHeader column={column as never} label="Name" />);

		await user.click(screen.getByRole("button", { name: /name/i }));

		expect(column.toggleSorting).toHaveBeenCalledWith(true);
	});

	it("calls toggleSorting with false when not sorted", async () => {
		const user = userEvent.setup();
		const column = createMockColumn(false);
		render(<SortableColumnHeader column={column as never} label="Name" />);

		await user.click(screen.getByRole("button", { name: /name/i }));

		expect(column.toggleSorting).toHaveBeenCalledWith(false);
	});

	it("calls toggleSorting with false when currently sorted descending", async () => {
		const user = userEvent.setup();
		const column = createMockColumn("desc");
		render(<SortableColumnHeader column={column as never} label="Name" />);

		await user.click(screen.getByRole("button", { name: /name/i }));

		expect(column.toggleSorting).toHaveBeenCalledWith(false);
	});

	it("shows sort indicator with opacity-100 when column is sorted", () => {
		const column = createMockColumn("asc");
		const { container } = render(
			<SortableColumnHeader column={column as never} label="Name" />,
		);

		const indicator = container.querySelector("span");
		expect(indicator?.className).toContain("opacity-100");
	});

	it("shows sort indicator with opacity-0 when column is not sorted", () => {
		const column = createMockColumn(false);
		const { container } = render(
			<SortableColumnHeader column={column as never} label="Name" />,
		);

		const indicator = container.querySelector("span");
		expect(indicator?.className).toContain("opacity-0");
		expect(indicator?.className).not.toContain("opacity-100 text-foreground");
	});
});
