import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphStatePopover } from "./flow-run-graph-state-popover";

describe("FlowRunGraphStatePopover", () => {
	const createStateSelection = (overrides = {}) => ({
		kind: "state" as const,
		id: "state-123",
		type: "COMPLETED" as const,
		name: "Completed",
		timestamp: new Date("2024-01-15T10:30:00Z"),
		position: { x: 100, y: 200, width: 20, height: 20 },
		...overrides,
	});

	it("renders state name with badge", () => {
		const selection = createStateSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("State")).toBeInTheDocument();
		expect(screen.getByText("Completed")).toBeInTheDocument();
	});

	it("renders timestamp", () => {
		const selection = createStateSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Occurred")).toBeInTheDocument();
	});

	it("renders different state types correctly", () => {
		const selection = createStateSelection({
			type: "FAILED",
			name: "Failed",
		});
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Failed")).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		const user = userEvent.setup();
		const selection = createStateSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		const closeButton = screen.getByRole("button", { name: "Close popover" });
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when clicking outside the popover", async () => {
		const user = userEvent.setup();
		const selection = createStateSelection();
		const onClose = vi.fn();

		render(
			<div>
				<div data-testid="outside">Outside</div>
				<FlowRunGraphStatePopover selection={selection} onClose={onClose} />
			</div>,
			{ wrapper: createWrapper() },
		);

		const outsideElement = screen.getByTestId("outside");
		await user.click(outsideElement);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when Escape key is pressed", async () => {
		const user = userEvent.setup();
		const selection = createStateSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		await user.keyboard("{Escape}");

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("returns null when position is not provided", () => {
		const selection = createStateSelection({ position: undefined });
		const onClose = vi.fn();

		const { container } = render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toBeNull();
	});

	it("positions the popover based on selection position", () => {
		const selection = createStateSelection({
			position: { x: 150, y: 250, width: 30, height: 30 },
		});
		const onClose = vi.fn();

		render(
			<FlowRunGraphStatePopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		const popover = screen.getByRole("button", { name: "Close popover" })
			.parentElement?.parentElement;
		expect(popover).toHaveStyle({
			left: "165px",
			top: "280px",
		});
	});
});
