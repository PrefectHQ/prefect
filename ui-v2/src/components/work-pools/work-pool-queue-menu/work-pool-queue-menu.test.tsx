import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueMenu } from "./work-pool-queue-menu";

// Mock the hook and dialog
vi.mock("./hooks/use-work-pool-queue-menu", () => ({
	useWorkPoolQueueMenu: vi.fn(() => ({
		menuItems: [
			{
				label: "Copy ID",
				icon: vi.fn(),
				action: vi.fn(),
				show: true,
			},
			{
				label: "Edit",
				icon: vi.fn(),
				action: vi.fn(),
				show: true,
			},
			{
				label: "Delete",
				icon: vi.fn(),
				action: vi.fn(),
				show: true,
				variant: "destructive",
			},
		],
		showDeleteDialog: false,
		setShowDeleteDialog: vi.fn(),
		triggerIcon: vi.fn(),
	})),
}));

vi.mock("./components/delete-work-pool-queue-dialog", () => ({
	DeleteWorkPoolQueueDialog: vi.fn(() => <div>Delete Dialog</div>),
}));

describe("WorkPoolQueueMenu", () => {
	it("renders menu button", () => {
		const queue = createFakeWorkPoolQueue({ name: "test-queue" });

		render(<WorkPoolQueueMenu queue={queue} />);

		expect(screen.getByRole("button")).toBeInTheDocument();
		expect(screen.getByText("Open menu")).toBeInTheDocument();
	});

	it("opens menu when button is clicked", () => {
		const queue = createFakeWorkPoolQueue({ name: "test-queue" });

		render(<WorkPoolQueueMenu queue={queue} />);

		const menuButton = screen.getByRole("button");
		fireEvent.click(menuButton);

		// Menu items should be visible after clicking
		expect(screen.getByText("Copy ID")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
		expect(screen.getByText("Delete")).toBeInTheDocument();
	});

	it("renders delete dialog", () => {
		const queue = createFakeWorkPoolQueue({ name: "test-queue" });

		render(<WorkPoolQueueMenu queue={queue} />);

		expect(screen.getByText("Delete Dialog")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const queue = createFakeWorkPoolQueue({ name: "test-queue" });

		const { container } = render(
			<WorkPoolQueueMenu queue={queue} className="custom-class" />,
		);

		const button = container.querySelector(".custom-class");
		expect(button).toBeInTheDocument();
	});

	it("renders destructive menu item with correct styling", () => {
		const queue = createFakeWorkPoolQueue({ name: "test-queue" });

		render(<WorkPoolQueueMenu queue={queue} />);

		const menuButton = screen.getByRole("button");
		fireEvent.click(menuButton);

		const deleteItem = screen.getByText("Delete").closest("div");
		expect(deleteItem).toHaveClass("text-destructive");
	});
});
