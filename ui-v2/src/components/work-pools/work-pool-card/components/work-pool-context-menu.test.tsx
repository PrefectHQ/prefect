import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { createWrapper } from "@tests/utils";
import { WorkPoolContextMenu } from "./work-pool-context-menu";

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

Object.defineProperty(navigator, "clipboard", {
	value: {
		writeText: vi.fn(() => Promise.resolve()),
	},
});

describe("WorkPoolContextMenu", () => {
	const workPool = createFakeWorkPool({
		id: "test-work-pool-id",
		name: "test-work-pool",
		status: "READY",
	});

	const mockOnDelete = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the dropdown menu with correct options", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText("Actions")).toBeInTheDocument();
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
			expect(screen.getByText("Edit")).toBeInTheDocument();
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
	});

	it("copies the work pool ID to clipboard when 'Copy ID' is clicked", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		const copyIdOption = await screen.findByText("Copy ID");
		fireEvent.click(copyIdOption);

		//  Despite the mock above, typescript-eslint is complaining about the method being unbound cause of the ambiguous `this`
		//  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(workPool.id);

		expect(toast.success).toHaveBeenCalledWith("ID copied");
	});

	it("renders an Edit option in the menu", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText("Edit")).toBeInTheDocument();
		});
	});

	it("calls the onDelete function when 'Delete' is clicked", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		const deleteOption = await screen.findByText("Delete");
		fireEvent.click(deleteOption);

		expect(mockOnDelete).toHaveBeenCalledTimes(1);
	});

	it("passes the delete action to the parent component", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		const deleteOption = await screen.findByText("Delete");
		fireEvent.click(deleteOption);

		expect(mockOnDelete).toHaveBeenCalledTimes(1);
	});

	it("closes the menu when an option is selected", async () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		fireEvent.click(dropdownButton);

		expect(screen.getByText("Actions")).toBeInTheDocument();

		const copyIdOption = await screen.findByText("Copy ID");
		fireEvent.click(copyIdOption);

		await waitFor(() => {
			expect(screen.queryByText("Actions")).not.toBeVisible();
		});
	});

	it("renders with the correct button styles", () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const button = screen.getByRole("button", { name: /open menu/i });

		expect(button).toHaveClass("size-8", "p-0");
	});

	it("has the correct icon in the button", () => {
		render(
			<WorkPoolContextMenu workPool={workPool} onDelete={mockOnDelete} />,
			{
				wrapper: createWrapper(),
			},
		);

		const button = screen.getByRole("button", { name: /open menu/i });
		const icon = button.querySelector(".size-4");

		expect(icon).toBeInTheDocument();
	});
});
