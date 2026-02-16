import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeleteConfirmationDialog } from "./delete-confirmation-dialog";

describe("DeleteConfirmationDialog", () => {
	const defaultProps = {
		isOpen: true,
		title: "Test Title",
		description: "Test Description",
		onConfirm: vi.fn(),
		onClose: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders dialog with correct title and description", () => {
		render(<DeleteConfirmationDialog {...defaultProps} />);

		expect(screen.getByText("Test Title")).toBeInTheDocument();
		expect(screen.getByText("Test Description")).toBeInTheDocument();
	});

	it("calls onClose when Cancel button is clicked", () => {
		render(<DeleteConfirmationDialog {...defaultProps} />);

		fireEvent.click(screen.getByText("Cancel"));
		expect(defaultProps.onClose).toHaveBeenCalled();
	});

	it("calls onConfirm when Delete button is clicked", () => {
		render(<DeleteConfirmationDialog {...defaultProps} />);

		fireEvent.click(screen.getByText("Delete"));
		expect(defaultProps.onConfirm).toHaveBeenCalled();
	});

	it("does not render when isOpen is false", () => {
		render(<DeleteConfirmationDialog {...defaultProps} isOpen={false} />);

		expect(screen.queryByText("Test Title")).not.toBeInTheDocument();
		expect(screen.queryByText("Test Description")).not.toBeInTheDocument();
	});

	describe("with confirmation text", () => {
		const propsWithConfirmText = {
			...defaultProps,
			confirmText: "test-item",
		};

		it("renders confirmation input when confirmText is provided", () => {
			render(<DeleteConfirmationDialog {...propsWithConfirmText} />);

			// Check for the input field and the strong element with the confirm text
			expect(screen.getByPlaceholderText("test-item")).toBeInTheDocument();
			expect(screen.getByRole("textbox")).toBeInTheDocument();

			// Check for the label by looking for the element with the expected for attribute
			const label = screen.getByLabelText(/Type.*test-item.*to confirm:/i);
			expect(label).toBeInTheDocument();
		});

		it("disables delete button when confirmation text doesn't match", () => {
			render(<DeleteConfirmationDialog {...propsWithConfirmText} />);

			const deleteButton = screen.getByText("Delete");
			expect(deleteButton).toBeDisabled();
		});

		it("enables delete button when confirmation text matches", async () => {
			const user = userEvent.setup();
			render(<DeleteConfirmationDialog {...propsWithConfirmText} />);

			const input = screen.getByPlaceholderText("test-item");
			await user.type(input, "test-item");

			const deleteButton = screen.getByText("Delete");
			expect(deleteButton).not.toBeDisabled();
		});

		it("calls onConfirm when confirmation text matches and delete is clicked", async () => {
			const user = userEvent.setup();
			render(<DeleteConfirmationDialog {...propsWithConfirmText} />);

			const input = screen.getByPlaceholderText("test-item");
			await user.type(input, "test-item");

			fireEvent.click(screen.getByText("Delete"));
			expect(defaultProps.onConfirm).toHaveBeenCalled();
		});

		it("clears input when onClose is called", async () => {
			const user = userEvent.setup();
			const onClose = vi.fn();
			const { rerender } = render(
				<DeleteConfirmationDialog
					{...propsWithConfirmText}
					onClose={onClose}
				/>,
			);

			const input = screen.getByPlaceholderText("test-item");
			await user.type(input, "some text");

			// Simulate closing the dialog
			fireEvent.click(screen.getByText("Cancel"));
			expect(onClose).toHaveBeenCalled();

			// Rerender with dialog closed and reopened to verify state reset
			rerender(
				<DeleteConfirmationDialog
					{...propsWithConfirmText}
					isOpen={false}
					onClose={onClose}
				/>,
			);
			rerender(
				<DeleteConfirmationDialog
					{...propsWithConfirmText}
					isOpen={true}
					onClose={onClose}
				/>,
			);

			const newInput = screen.getByPlaceholderText("test-item");
			expect(newInput).toHaveValue("");
		});
	});

	describe("with loading state", () => {
		const propsWithLoading = {
			...defaultProps,
			isLoading: true,
			loadingText: "Removing...",
		};

		it("shows loading text when isLoading is true", () => {
			render(<DeleteConfirmationDialog {...propsWithLoading} />);

			expect(screen.getByText("Removing...")).toBeInTheDocument();
			expect(screen.queryByText("Delete")).not.toBeInTheDocument();
		});

		it("disables delete button when isLoading is true", () => {
			render(<DeleteConfirmationDialog {...propsWithLoading} />);

			const deleteButton = screen.getByText("Removing...");
			expect(deleteButton).toBeDisabled();
		});
	});
});
