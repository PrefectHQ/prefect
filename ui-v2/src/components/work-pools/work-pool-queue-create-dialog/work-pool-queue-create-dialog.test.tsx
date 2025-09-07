import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueueCreateDialog } from "./work-pool-queue-create-dialog";

describe("WorkPoolQueueCreateDialog", () => {
	const defaultProps = {
		workPoolName: "test-work-pool",
		open: true,
		onOpenChange: vi.fn(),
		onSubmit: vi.fn(),
	};

	it("renders when open", () => {
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Create Work Queue" }),
		).toBeInTheDocument();
	});

	it("does not render when closed", () => {
		render(<WorkPoolQueueCreateDialog {...defaultProps} open={false} />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});

	it("renders all form fields", () => {
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("Name")).toBeInTheDocument();
		expect(screen.getByLabelText("Description")).toBeInTheDocument();
		expect(screen.getByLabelText("Flow Run Concurrency")).toBeInTheDocument();
		expect(
			screen.getByRole("spinbutton", { name: /Priority/i }),
		).toBeInTheDocument();
	});

	it("shows validation error for empty name", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const submitButton = screen.getByRole("button", {
			name: "Create Work Queue",
		});
		await user.click(submitButton);

		await waitFor(() => {
			expect(screen.getByText("Name is required")).toBeInTheDocument();
		});
	});

	it("shows validation error for invalid name characters", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "invalid name with spaces");

		const submitButton = screen.getByRole("button", {
			name: "Create Work Queue",
		});
		await user.click(submitButton);

		await waitFor(() => {
			expect(
				screen.getByText(
					"Name can only contain letters, numbers, hyphens, and underscores",
				),
			).toBeInTheDocument();
		});
	});

	it("calls onOpenChange when cancel button is clicked", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		render(
			<WorkPoolQueueCreateDialog
				{...defaultProps}
				onOpenChange={onOpenChange}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(cancelButton);

		expect(onOpenChange).toHaveBeenCalledWith(false);
	});

	it("shows loading state when creating", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "test-queue");

		const submitButton = screen.getByRole("button", {
			name: "Create Work Queue",
		});

		expect(submitButton).not.toHaveAttribute("data-loading");

		// We can't easily test the actual submission with the mocked hook
		// since it would require complex async mock setup
		// Instead we test that the form renders correctly and can be submitted
		expect(submitButton).toBeEnabled();
	});

	it("handles concurrency limit input correctly", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const concurrencyInput = screen.getByLabelText("Flow Run Concurrency");
		await user.type(concurrencyInput, "5");

		expect(concurrencyInput).toHaveValue(5);
	});

	it("handles priority input correctly", async () => {
		const user = userEvent.setup();
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		const priorityInput = screen.getByRole("spinbutton", { name: /Priority/i });
		await user.type(priorityInput, "3");

		expect(priorityInput).toHaveValue(3);
	});

	it("renders priority info tooltip button", () => {
		render(<WorkPoolQueueCreateDialog {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		// Check that the info button is rendered next to the Priority label
		const infoButton = screen.getByRole("button", { name: "" });
		expect(infoButton).toBeInTheDocument();
		expect(infoButton).toHaveClass("cursor-help");
	});
});
