import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChangeStateDialog, useChangeStateDialog } from "./index";

describe("ChangeStateDialog", () => {
	const defaultProps = {
		open: true,
		onOpenChange: vi.fn(),
		currentState: { type: "RUNNING", name: "Running" },
		label: "Task Run",
		onConfirm: vi.fn(),
	};

	beforeEach(() => {
		vi.clearAllMocks();
		mockPointerEvents();
	});

	it("renders dialog with correct title", () => {
		render(<ChangeStateDialog {...defaultProps} />);

		expect(screen.getByText("Change Task Run State")).toBeInTheDocument();
	});

	it("displays current state as StateBadge", () => {
		render(<ChangeStateDialog {...defaultProps} />);

		expect(screen.getByText("Current State")).toBeInTheDocument();
		expect(screen.getByText("Running")).toBeInTheDocument();
	});

	it("does not display current state when currentState is null", () => {
		render(<ChangeStateDialog {...defaultProps} currentState={null} />);

		expect(screen.queryByText("Current State")).not.toBeInTheDocument();
	});

	it("renders state select with terminal states only", async () => {
		const user = userEvent.setup();
		render(<ChangeStateDialog {...defaultProps} />);

		await user.click(screen.getByRole("combobox"));

		expect(screen.getByRole("option", { name: /completed/i })).toBeVisible();
		expect(screen.getByRole("option", { name: /failed/i })).toBeVisible();
		expect(screen.getByRole("option", { name: /cancelled/i })).toBeVisible();
		expect(screen.getByRole("option", { name: /crashed/i })).toBeVisible();

		expect(screen.queryByRole("option", { name: /running/i })).toBeNull();
		expect(screen.queryByRole("option", { name: /scheduled/i })).toBeNull();
		expect(screen.queryByRole("option", { name: /pending/i })).toBeNull();
	});

	it("has confirm button disabled when no state is selected", () => {
		render(<ChangeStateDialog {...defaultProps} />);

		const confirmButton = screen.getByRole("button", { name: "Change" });
		expect(confirmButton).toBeDisabled();
	});

	it("enables confirm button when state is selected", async () => {
		const user = userEvent.setup();
		render(<ChangeStateDialog {...defaultProps} />);

		await user.click(screen.getByRole("combobox"));
		await user.click(screen.getByRole("option", { name: /completed/i }));

		const confirmButton = screen.getByRole("button", { name: "Change" });
		expect(confirmButton).not.toBeDisabled();
	});

	it("calls onConfirm with selected state when confirm button is clicked", async () => {
		const user = userEvent.setup();
		const onConfirm = vi.fn();
		render(<ChangeStateDialog {...defaultProps} onConfirm={onConfirm} />);

		await user.click(screen.getByRole("combobox"));
		await user.click(screen.getByRole("option", { name: /completed/i }));
		await user.click(screen.getByRole("button", { name: "Change" }));

		expect(onConfirm).toHaveBeenCalledWith({
			type: "COMPLETED",
			message: undefined,
		});
	});

	it("calls onConfirm with message when provided", async () => {
		const user = userEvent.setup();
		const onConfirm = vi.fn();
		render(<ChangeStateDialog {...defaultProps} onConfirm={onConfirm} />);

		await user.click(screen.getByRole("combobox"));
		await user.click(screen.getByRole("option", { name: /failed/i }));

		const messageInput = screen.getByPlaceholderText(
			"State changed manually via UI",
		);
		await user.type(messageInput, "Test reason");

		await user.click(screen.getByRole("button", { name: "Change" }));

		expect(onConfirm).toHaveBeenCalledWith({
			type: "FAILED",
			message: "Test reason",
		});
	});

	it("calls onOpenChange when Close button is clicked", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		render(<ChangeStateDialog {...defaultProps} onOpenChange={onOpenChange} />);

		const closeButtons = screen.getAllByRole("button", { name: "Close" });
		const footerCloseButton = closeButtons.find(
			(btn) => btn.textContent === "Close",
		);
		expect(footerCloseButton).toBeDefined();
		await user.click(footerCloseButton!);

		expect(onOpenChange).toHaveBeenCalledWith(false);
	});

	it("does not render when open is false", () => {
		render(<ChangeStateDialog {...defaultProps} open={false} />);

		expect(screen.queryByText("Change Task Run State")).not.toBeInTheDocument();
	});

	describe("with loading state", () => {
		it("disables confirm button when isLoading is true", async () => {
			const user = userEvent.setup();
			render(<ChangeStateDialog {...defaultProps} isLoading />);

			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: /completed/i }));

			const allButtons = screen.getAllByRole("button");
			const confirmButton = allButtons.find(
				(btn) =>
					btn.classList.contains("bg-primary") &&
					btn.getAttribute("type") === "button",
			);
			expect(confirmButton).toBeDefined();
			expect(confirmButton).toBeDisabled();
		});

		it("disables close button when isLoading is true", () => {
			render(<ChangeStateDialog {...defaultProps} isLoading />);

			const closeButtons = screen.getAllByRole("button", { name: "Close" });
			const footerCloseButton = closeButtons.find(
				(btn) => btn.textContent === "Close",
			);
			expect(footerCloseButton).toBeDefined();
			expect(footerCloseButton).toBeDisabled();
		});
	});

	describe("form state reset", () => {
		it("resets form state when dialog closes", async () => {
			const user = userEvent.setup();
			const { rerender } = render(<ChangeStateDialog {...defaultProps} />);

			await user.click(screen.getByRole("combobox"));
			await user.click(screen.getByRole("option", { name: /completed/i }));

			const messageInput = screen.getByPlaceholderText(
				"State changed manually via UI",
			);
			await user.type(messageInput, "Test reason");

			rerender(<ChangeStateDialog {...defaultProps} open={false} />);
			rerender(<ChangeStateDialog {...defaultProps} open={true} />);

			const newMessageInput = screen.getByPlaceholderText(
				"State changed manually via UI",
			);
			expect(newMessageInput).toHaveValue("");

			const confirmButton = screen.getByRole("button", { name: "Change" });
			expect(confirmButton).toBeDisabled();
		});
	});
});

describe("useChangeStateDialog", () => {
	const TestComponent = () => {
		const { open, onOpenChange, openDialog, closeDialog } =
			useChangeStateDialog();

		return (
			<div>
				<span data-testid="open-state">{open.toString()}</span>
				<button type="button" onClick={openDialog}>
					Open
				</button>
				<button type="button" onClick={closeDialog}>
					Close
				</button>
				<button type="button" onClick={() => onOpenChange(true)}>
					Set True
				</button>
				<button type="button" onClick={() => onOpenChange(false)}>
					Set False
				</button>
			</div>
		);
	};

	it("initializes with open as false", () => {
		render(<TestComponent />);

		expect(screen.getByTestId("open-state")).toHaveTextContent("false");
	});

	it("openDialog sets open to true", async () => {
		const user = userEvent.setup();
		render(<TestComponent />);

		await user.click(screen.getByRole("button", { name: "Open" }));

		expect(screen.getByTestId("open-state")).toHaveTextContent("true");
	});

	it("closeDialog sets open to false", async () => {
		const user = userEvent.setup();
		render(<TestComponent />);

		await user.click(screen.getByRole("button", { name: "Open" }));
		expect(screen.getByTestId("open-state")).toHaveTextContent("true");

		await user.click(screen.getByRole("button", { name: "Close" }));
		expect(screen.getByTestId("open-state")).toHaveTextContent("false");
	});

	it("onOpenChange updates open state", async () => {
		const user = userEvent.setup();
		render(<TestComponent />);

		await user.click(screen.getByRole("button", { name: "Set True" }));
		expect(screen.getByTestId("open-state")).toHaveTextContent("true");

		await user.click(screen.getByRole("button", { name: "Set False" }));
		expect(screen.getByTestId("open-state")).toHaveTextContent("false");
	});
});
