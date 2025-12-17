import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SaveFilterDialog } from "./save-filter-dialog";

describe("SaveFilterDialog", () => {
	const defaultProps = {
		open: true,
		onOpenChange: vi.fn(),
		onSave: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders dialog with correct title and description", () => {
		render(<SaveFilterDialog {...defaultProps} />);

		expect(screen.getByText("Save Filter")).toBeInTheDocument();
		expect(
			screen.getByText(
				"Save your current filter configuration for quick access later.",
			),
		).toBeInTheDocument();
	});

	it("renders input field for filter name", () => {
		render(<SaveFilterDialog {...defaultProps} />);

		expect(screen.getByLabelText("Filter Name")).toBeInTheDocument();
		expect(
			screen.getByPlaceholderText("e.g., Failed runs this week"),
		).toBeInTheDocument();
	});

	it("does not render when open is false", () => {
		render(<SaveFilterDialog {...defaultProps} open={false} />);

		expect(screen.queryByText("Save Filter")).not.toBeInTheDocument();
	});

	it("calls onOpenChange when Cancel button is clicked", async () => {
		const user = userEvent.setup();
		render(<SaveFilterDialog {...defaultProps} />);

		await user.click(screen.getByRole("button", { name: /cancel/i }));

		expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
	});

	it("calls onSave with filter name when Save button is clicked", async () => {
		const user = userEvent.setup();
		render(<SaveFilterDialog {...defaultProps} />);

		const input = screen.getByPlaceholderText("e.g., Failed runs this week");
		await user.type(input, "My Filter");

		await user.click(screen.getByRole("button", { name: /save/i }));

		expect(defaultProps.onSave).toHaveBeenCalledWith("My Filter");
	});

	it("clears input when dialog is closed and reopened", async () => {
		const user = userEvent.setup();
		const { rerender } = render(<SaveFilterDialog {...defaultProps} />);

		const input = screen.getByPlaceholderText("e.g., Failed runs this week");
		await user.type(input, "My Filter");

		// Close the dialog
		rerender(<SaveFilterDialog {...defaultProps} open={false} />);

		// Reopen the dialog
		rerender(<SaveFilterDialog {...defaultProps} open={true} />);

		await waitFor(() => {
			const newInput = screen.getByPlaceholderText(
				"e.g., Failed runs this week",
			);
			expect(newInput).toHaveValue("");
		});
	});
});
