import { fireEvent, render, screen } from "@testing-library/react";
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

	it("calls both onConfirm and onClose when Delete button is clicked", () => {
		render(<DeleteConfirmationDialog {...defaultProps} />);

		fireEvent.click(screen.getByText("Delete"));
		expect(defaultProps.onConfirm).toHaveBeenCalled();
		expect(defaultProps.onClose).toHaveBeenCalled();
	});

	it("does not render when isOpen is false", () => {
		render(<DeleteConfirmationDialog {...defaultProps} isOpen={false} />);

		expect(screen.queryByText("Test Title")).not.toBeInTheDocument();
		expect(screen.queryByText("Test Description")).not.toBeInTheDocument();
	});
});
