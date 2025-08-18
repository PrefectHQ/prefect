import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueToggle } from "./work-pool-queue-toggle";

// Mock the hook
vi.mock("./hooks/use-work-pool-queue-toggle", () => ({
	useWorkPoolQueueToggle: vi.fn(() => ({
		handleToggle: vi.fn(),
		isLoading: false,
	})),
}));

describe("WorkPoolQueueToggle", () => {
	it("renders toggle switch for non-default queue", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "ready",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).toBeInTheDocument();
		expect(screen.getByRole("switch")).toBeChecked(); // Ready queue should be checked (not paused)
	});

	it("renders toggle switch unchecked for paused queue", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "paused",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).toBeInTheDocument();
		expect(screen.getByRole("switch")).not.toBeChecked();
	});

	it("disables toggle for default queue", () => {
		const queue = createFakeWorkPoolQueue({
			name: "default",
			status: "ready",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).toBeDisabled();
	});

	it("disables toggle when disabled prop is true", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "ready",
		});

		render(<WorkPoolQueueToggle queue={queue} disabled={true} />);

		expect(screen.getByRole("switch")).toBeDisabled();
	});

	it("shows correct tooltip for default queue", async () => {
		const queue = createFakeWorkPoolQueue({
			name: "default",
			status: "ready",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		// Hover over the toggle to show tooltip
		fireEvent.mouseEnter(screen.getByRole("switch"));

		expect(
			await screen.findByText("Default queue cannot be paused"),
		).toBeInTheDocument();
	});

	it("shows correct tooltip for regular queue", async () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "ready",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		// Hover over the toggle to show tooltip
		fireEvent.mouseEnter(screen.getByRole("switch"));

		expect(
			await screen.findByText("Pause or resume this work pool queue"),
		).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "ready",
		});

		const { container } = render(
			<WorkPoolQueueToggle queue={queue} className="custom-class" />,
		);

		const switchElement = container.querySelector(".custom-class");
		expect(switchElement).toBeInTheDocument();
	});
});
