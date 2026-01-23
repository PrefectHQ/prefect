import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphEventPopover } from "./flow-run-graph-event-popover";

describe("FlowRunGraphEventPopover", () => {
	const createEventSelection = (overrides = {}) => ({
		kind: "event" as const,
		id: "event-123",
		occurred: new Date("2024-01-15T10:30:00Z"),
		position: { x: 100, y: 200, width: 20, height: 20 },
		...overrides,
	});

	const mockEventResponse = {
		events: [
			{
				id: "event-123",
				occurred: "2024-01-15T10:30:00Z",
				received: "2024-01-15T10:30:01Z",
				event: "prefect.flow-run.completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
					"prefect.resource.name": "my-flow-run",
				},
				payload: {},
				related: [],
			},
		],
		total: 1,
		next_page: null,
	};

	const setupMockServer = () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(mockEventResponse);
			}),
		);
	};

	it("renders event details correctly", async () => {
		setupMockServer();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByText("Event")).toBeInTheDocument();
		expect(
			await screen.findByText("prefect.flow-run.completed"),
		).toBeInTheDocument();
		expect(screen.getByText("Occurred")).toBeInTheDocument();
		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("my-flow-run")).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		const closeButton = await screen.findByRole("button", {
			name: "Close popover",
		});
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when clicking outside the popover", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<div>
				<div data-testid="outside">Outside</div>
				<FlowRunGraphEventPopover selection={selection} onClose={onClose} />
			</div>,
			{ wrapper: createWrapper() },
		);

		const outsideElement = screen.getByTestId("outside");
		await user.click(outsideElement);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when Escape key is pressed", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		await user.keyboard("{Escape}");

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("returns null when position is not provided", () => {
		setupMockServer();
		const selection = createEventSelection({ position: undefined });
		const onClose = vi.fn();

		const { container } = render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toBeNull();
	});

	it("positions the popover based on selection position", async () => {
		setupMockServer();
		const selection = createEventSelection({
			position: { x: 150, y: 250, width: 30, height: 30 },
		});
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		const closeButton = await screen.findByRole("button", {
			name: "Close popover",
		});
		const popover = closeButton.parentElement?.parentElement;
		expect(popover).toHaveStyle({
			left: "165px",
			top: "280px",
		});
	});

	it("shows loading state while fetching event details", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(mockEventResponse);
			}),
		);

		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("button", { name: "Close popover" })).toBeVisible();
		expect(
			await screen.findByText("prefect.flow-run.completed"),
		).toBeInTheDocument();
	});

	it("displays resource id when resource name is not available", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json({
					events: [
						{
							id: "event-123",
							occurred: "2024-01-15T10:30:00Z",
							received: "2024-01-15T10:30:01Z",
							event: "prefect.flow-run.started",
							resource: {
								"prefect.resource.id": "prefect.flow-run.xyz789",
							},
							payload: {},
							related: [],
						},
					],
					total: 1,
					next_page: null,
				});
			}),
		);

		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		expect(
			await screen.findByText("prefect.flow-run.xyz789"),
		).toBeInTheDocument();
	});
});
