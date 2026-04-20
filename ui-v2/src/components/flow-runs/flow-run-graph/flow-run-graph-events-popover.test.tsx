import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphEventsPopover } from "./flow-run-graph-events-popover";

describe("FlowRunGraphEventsPopover", () => {
	const createEventsSelection = (overrides = {}) => ({
		kind: "events" as const,
		ids: ["event-1", "event-2", "event-3"],
		occurred: new Date("2024-01-15T10:30:00Z"),
		position: { x: 100, y: 200, width: 20, height: 20 },
		...overrides,
	});

	const createMockEventResponse = (id: string, eventName: string) => ({
		events: [
			{
				id,
				occurred: "2024-01-15T10:30:00Z",
				received: "2024-01-15T10:30:01Z",
				event: eventName,
				resource: {
					"prefect.resource.id": `prefect.flow-run.${id}`,
					"prefect.resource.name": "my-flow-run",
				},
				payload: {},
				related: [],
			},
		],
		total: 1,
		next_page: null,
	});

	it("renders event count in header", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(
					createMockEventResponse("event-1", "prefect.flow-run.completed"),
				);
			}),
		);

		const selection = createEventsSelection();
		render(
			<FlowRunGraphEventsPopover selection={selection} onClose={vi.fn()} />,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByText("3 Events")).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(
					createMockEventResponse("event-1", "prefect.flow-run.completed"),
				);
			}),
		);

		const user = userEvent.setup();
		const onClose = vi.fn();
		const selection = createEventsSelection();

		render(
			<FlowRunGraphEventsPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		const closeButton = screen.getByRole("button", { name: "Close popover" });
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("returns null when position is not provided", () => {
		const selection = createEventsSelection({ position: undefined });
		const { container } = render(
			<FlowRunGraphEventsPopover selection={selection} onClose={vi.fn()} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toBeNull();
	});

	it("displays loading state while fetching events", () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(createMockEventResponse("event-1", "test"));
			}),
		);

		const selection = createEventsSelection();
		render(
			<FlowRunGraphEventsPopover selection={selection} onClose={vi.fn()} />,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("3 Events")).toBeInTheDocument();
	});

	it("calls onClose when clicking outside the popover", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(
					createMockEventResponse("event-1", "prefect.flow-run.completed"),
				);
			}),
		);

		const user = userEvent.setup();
		const selection = createEventsSelection();
		const onClose = vi.fn();

		render(
			<div>
				<div data-testid="outside">Outside</div>
				<FlowRunGraphEventsPopover selection={selection} onClose={onClose} />
			</div>,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		const outsideElement = screen.getByTestId("outside");
		await user.click(outsideElement);

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("calls onClose when Escape key is pressed", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(
					createMockEventResponse("event-1", "prefect.flow-run.completed"),
				);
			}),
		);

		const user = userEvent.setup();
		const selection = createEventsSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventsPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		await user.keyboard("{Escape}");

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("positions the anchor based on selection position", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(
					createMockEventResponse("event-1", "prefect.flow-run.completed"),
				);
			}),
		);

		const selection = createEventsSelection({
			position: { x: 150, y: 250, width: 30, height: 30 },
		});
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventsPopover selection={selection} onClose={onClose} />,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		const anchor = document.querySelector('[data-slot="popover-anchor"]');
		expect(anchor).toHaveStyle({
			left: "165px",
			top: "280px",
		});
	});
});
