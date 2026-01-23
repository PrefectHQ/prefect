import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphArtifactsPopover } from "./flow-run-graph-artifacts-popover";

describe("FlowRunGraphArtifactsPopover", () => {
	const createArtifact = (overrides = {}) => ({
		id: "artifact-123",
		key: "my-artifact",
		type: "result",
		...overrides,
	});

	const defaultPosition = { x: 100, y: 200, width: 20, height: 20 };

	it("renders list of artifacts correctly", () => {
		const artifacts = [
			createArtifact({
				id: "artifact-1",
				key: "first-artifact",
				type: "result",
			}),
			createArtifact({
				id: "artifact-2",
				key: "second-artifact",
				type: "markdown",
			}),
		];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Artifacts")).toBeInTheDocument();
		expect(screen.getByText("first-artifact")).toBeInTheDocument();
		expect(screen.getByText("second-artifact")).toBeInTheDocument();
		expect(screen.getByText("result")).toBeInTheDocument();
		expect(screen.getByText("markdown")).toBeInTheDocument();
	});

	it("shows 'Unnamed' for artifacts without keys", () => {
		const artifacts = [
			createArtifact({ id: "artifact-1", key: null, type: "result" }),
		];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Unnamed")).toBeInTheDocument();
	});

	it("View button calls onViewArtifact with correct ID", async () => {
		const user = userEvent.setup();
		const artifacts = [
			createArtifact({ id: "artifact-123", key: "my-artifact" }),
		];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		const viewButton = screen.getByRole("button", { name: "View" });
		await user.click(viewButton);

		expect(onViewArtifact).toHaveBeenCalledTimes(1);
		expect(onViewArtifact).toHaveBeenCalledWith("artifact-123");
	});

	it("calls onClose when close button is clicked", async () => {
		const user = userEvent.setup();
		const artifacts = [createArtifact()];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		const closeButton = screen.getByRole("button", { name: "Close popover" });
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when Escape key is pressed", async () => {
		const user = userEvent.setup();
		const artifacts = [createArtifact()];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.keyboard("{Escape}");

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("calls onClose when clicking outside the popover", async () => {
		const user = userEvent.setup();
		const artifacts = [createArtifact()];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<div>
				<div data-testid="outside">Outside</div>
				<FlowRunGraphArtifactsPopover
					artifacts={artifacts}
					position={defaultPosition}
					onClose={onClose}
					onViewArtifact={onViewArtifact}
				/>
			</div>,
			{ wrapper: createWrapper() },
		);

		const outsideElement = screen.getByTestId("outside");
		await user.click(outsideElement);

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("positions the anchor based on position prop", () => {
		const artifacts = [createArtifact()];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const position = { x: 150, y: 250, width: 30, height: 30 };

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={position}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		const anchor = document.querySelector('[data-slot="popover-anchor"]');
		expect(anchor).toHaveStyle({
			left: "165px",
			top: "280px",
		});
	});

	it("renders multiple View buttons for multiple artifacts", async () => {
		const user = userEvent.setup();
		const artifacts = [
			createArtifact({ id: "artifact-1", key: "first" }),
			createArtifact({ id: "artifact-2", key: "second" }),
			createArtifact({ id: "artifact-3", key: "third" }),
		];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		const viewButtons = screen.getAllByRole("button", { name: "View" });
		expect(viewButtons).toHaveLength(3);

		await user.click(viewButtons[1]);
		expect(onViewArtifact).toHaveBeenCalledWith("artifact-2");
	});

	it("does not show type when artifact type is null", () => {
		const artifacts = [
			createArtifact({ id: "artifact-1", key: "my-artifact", type: null }),
		];
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();

		render(
			<FlowRunGraphArtifactsPopover
				artifacts={artifacts}
				position={defaultPosition}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("my-artifact")).toBeInTheDocument();
		expect(screen.queryByText("result")).not.toBeInTheDocument();
	});
});
