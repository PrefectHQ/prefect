import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
			status: "READY",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).toBeInTheDocument();
		expect(screen.getByRole("switch")).toBeChecked(); // Ready queue should be checked (not paused)
	});

	it("renders toggle switch unchecked for paused queue", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "PAUSED",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).toBeInTheDocument();
		expect(screen.getByRole("switch")).not.toBeChecked();
	});

	it("enables toggle for default queue", () => {
		const queue = createFakeWorkPoolQueue({
			name: "default",
			status: "READY",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		expect(screen.getByRole("switch")).not.toBeDisabled();
	});

	it("disables toggle when disabled prop is true", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "READY",
		});

		render(<WorkPoolQueueToggle queue={queue} disabled={true} />);

		expect(screen.getByRole("switch")).toBeDisabled();
	});

	it("shows correct tooltip for default queue", async () => {
		const user = userEvent.setup();
		const queue = createFakeWorkPoolQueue({
			name: "default",
			status: "READY",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		// Hover over the toggle to show tooltip
		await user.hover(screen.getByRole("switch"));

		const tooltipTexts = await screen.findAllByText(
			"Pause or resume this work pool queue",
		);
		expect(tooltipTexts.length).toBeGreaterThan(0);
	});

	it("shows correct tooltip for regular queue", async () => {
		const user = userEvent.setup();
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "READY",
		});

		render(<WorkPoolQueueToggle queue={queue} />);

		// Hover over the toggle to show tooltip
		await user.hover(screen.getByRole("switch"));

		const tooltipTexts = await screen.findAllByText(
			"Pause or resume this work pool queue",
		);
		expect(tooltipTexts.length).toBeGreaterThan(0);
	});

	it("applies custom className", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			status: "READY",
		});

		const { container } = render(
			<WorkPoolQueueToggle queue={queue} className="custom-class" />,
		);

		const switchElement = container.querySelector(".custom-class");
		expect(switchElement).toBeInTheDocument();
	});
});
