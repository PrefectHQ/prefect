import type { ArtifactsSelection } from "@prefecthq/graphs";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphArtifactsPopover } from "./flow-run-graph-artifacts-popover";

describe("FlowRunGraphArtifactsPopover", () => {
	const createSelection = (
		ids: string[],
		position = { x: 100, y: 200, width: 20, height: 20 },
	): ArtifactsSelection => ({
		kind: "artifacts",
		ids,
		position,
	});

	const createArtifactResponse = (overrides = {}) => ({
		id: "artifact-123",
		key: "my-artifact",
		type: "result",
		created: "2024-01-01T00:00:00Z",
		updated: "2024-01-01T00:00:00Z",
		...overrides,
	});

	const setupMockArtifacts = (
		artifacts: ReturnType<typeof createArtifactResponse>[],
	) => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json(artifacts);
			}),
		);
	};

	it("renders list of artifacts correctly", async () => {
		const artifacts = [
			createArtifactResponse({
				id: "artifact-1",
				key: "first-artifact",
				type: "result",
			}),
			createArtifactResponse({
				id: "artifact-2",
				key: "second-artifact",
				type: "markdown",
			}),
		];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-1", "artifact-2"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Artifacts")).toBeInTheDocument();

		await waitFor(() => {
			expect(screen.getByText("first-artifact")).toBeInTheDocument();
		});
		expect(screen.getByText("second-artifact")).toBeInTheDocument();
		expect(screen.getByText("result")).toBeInTheDocument();
		expect(screen.getByText("markdown")).toBeInTheDocument();
	});

	it("shows 'Unnamed' for artifacts without keys", async () => {
		const artifacts = [
			createArtifactResponse({ id: "artifact-1", key: null, type: "result" }),
		];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-1"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("Unnamed")).toBeInTheDocument();
		});
	});

	it("View button calls onViewArtifact with correct ID", async () => {
		const user = userEvent.setup();
		const artifacts = [
			createArtifactResponse({ id: "artifact-123", key: "my-artifact" }),
		];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-123"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
		});

		const viewButton = screen.getByRole("button", { name: "View" });
		await user.click(viewButton);

		expect(onViewArtifact).toHaveBeenCalledTimes(1);
		expect(onViewArtifact).toHaveBeenCalledWith("artifact-123");
	});

	it("calls onClose when close button is clicked", async () => {
		const user = userEvent.setup();
		const artifacts = [createArtifactResponse()];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-123"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
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
		const artifacts = [createArtifactResponse()];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-123"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
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
		const artifacts = [createArtifactResponse()];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-123"]);

		render(
			<div>
				<div data-testid="outside">Outside</div>
				<FlowRunGraphArtifactsPopover
					selection={selection}
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

	it("positions the anchor based on selection position", () => {
		const artifacts = [createArtifactResponse()];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-123"], {
			x: 150,
			y: 250,
			width: 30,
			height: 30,
		});

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
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
			createArtifactResponse({ id: "artifact-1", key: "first" }),
			createArtifactResponse({ id: "artifact-2", key: "second" }),
			createArtifactResponse({ id: "artifact-3", key: "third" }),
		];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection([
			"artifact-1",
			"artifact-2",
			"artifact-3",
		]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getAllByRole("button", { name: "View" })).toHaveLength(3);
		});

		const viewButtons = screen.getAllByRole("button", { name: "View" });
		await user.click(viewButtons[1]);
		expect(onViewArtifact).toHaveBeenCalledWith("artifact-2");
	});

	it("does not show type when artifact type is null", async () => {
		const artifacts = [
			createArtifactResponse({
				id: "artifact-1",
				key: "my-artifact",
				type: null,
			}),
		];
		setupMockArtifacts(artifacts);

		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-1"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("my-artifact")).toBeInTheDocument();
		});
		expect(screen.queryByText("result")).not.toBeInTheDocument();
	});

	it("shows loading state while fetching artifacts", () => {
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection = createSelection(["artifact-1"]);

		render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Artifacts")).toBeInTheDocument();
	});

	it("returns null when position is not provided", () => {
		const onClose = vi.fn();
		const onViewArtifact = vi.fn();
		const selection: ArtifactsSelection = {
			kind: "artifacts",
			ids: ["artifact-1"],
		};

		const { container } = render(
			<FlowRunGraphArtifactsPopover
				selection={selection}
				onClose={onClose}
				onViewArtifact={onViewArtifact}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toBeNull();
	});
});
