import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { EventsCount } from "@/api/events";
import { EventsCombobox } from "./events-combobox";

const MOCK_EVENT_COUNTS: EventsCount[] = [
	{
		value: "prefect.flow-run.Completed",
		label: "prefect.flow-run.Completed",
		count: 10,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-01T23:59:59Z",
	},
	{
		value: "prefect.flow-run.Failed",
		label: "prefect.flow-run.Failed",
		count: 5,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-01T23:59:59Z",
	},
	{
		value: "prefect.task-run.Completed",
		label: "prefect.task-run.Completed",
		count: 20,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-01T23:59:59Z",
	},
	{
		value: "prefect.task-run.Failed",
		label: "prefect.task-run.Failed",
		count: 3,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-01T23:59:59Z",
	},
];

const mockEventsCountAPI = () => {
	server.use(
		http.post(buildApiUrl("/events/count-by/:countable"), () => {
			return HttpResponse.json(MOCK_EVENT_COUNTS);
		}),
	);
};

beforeAll(() => {
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		value: vi.fn(),
		configurable: true,
		writable: true,
	});
});

beforeEach(() => {
	mockEventsCountAPI();
});

describe("EventsCombobox", () => {
	it("renders with empty message when no events selected", async () => {
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("All events")).toBeInTheDocument();
		});
	});

	it("renders with custom empty message", async () => {
		render(
			<EventsCombobox
				selectedEvents={[]}
				onToggleEvent={vi.fn()}
				emptyMessage="Select events"
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("Select events")).toBeInTheDocument();
		});
	});

	it("displays selected events", async () => {
		render(
			<EventsCombobox
				selectedEvents={["prefect.flow-run.Completed", "prefect.task-run.*"]}
				onToggleEvent={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText("prefect.flow-run.Completed, prefect.task-run.*"),
			).toBeInTheDocument();
		});
	});

	it("displays selected events with overflow indicator", async () => {
		render(
			<EventsCombobox
				selectedEvents={[
					"prefect.flow-run.Completed",
					"prefect.flow-run.Failed",
					"prefect.task-run.Completed",
				]}
				onToggleEvent={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("+1")).toBeInTheDocument();
		});
	});

	it("opens dropdown and shows search input", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeInTheDocument();
			expect(
				screen.getByPlaceholderText("Search events..."),
			).toBeInTheDocument();
		});
	});

	it("displays event names from API", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.Completed" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.Failed" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.task-run.Completed" }),
			).toBeInTheDocument();
		});
	});

	it("generates and displays wildcard prefixes", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			// Should generate prefect.flow-run.* and prefect.task-run.* since each has 2 events
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.task-run.*" }),
			).toBeInTheDocument();
		});
	});

	it("filters options based on search", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "flow-run");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.Completed" }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "prefect.task-run.*" }),
			).not.toBeInTheDocument();
		});
	});

	it("shows custom option when search doesn't match existing options", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "custom.event.name");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /Add.*custom\.event\.name/ }),
			).toBeInTheDocument();
		});
	});

	it("calls onToggleEvent when selecting an event", async () => {
		const onToggleEvent = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsCombobox selectedEvents={[]} onToggleEvent={onToggleEvent} />,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText(
			"prefect.flow-run.Completed",
		);
		await user.click(option);

		expect(onToggleEvent).toHaveBeenCalledWith("prefect.flow-run.Completed");
	});

	it("calls onToggleEvent when selecting a custom event", async () => {
		const onToggleEvent = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsCombobox selectedEvents={[]} onToggleEvent={onToggleEvent} />,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "my.custom.event");

		const listbox = await screen.findByRole("listbox");
		const customOption = await within(listbox).findByText(
			/Add.*my\.custom\.event/,
		);
		await user.click(customOption);

		expect(onToggleEvent).toHaveBeenCalledWith("my.custom.event");
	});

	it("clears search after selecting an event", async () => {
		const user = userEvent.setup();
		render(<EventsCombobox selectedEvents={[]} onToggleEvent={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "flow");

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText(
			"prefect.flow-run.Completed",
		);
		await user.click(option);

		await waitFor(() => {
			expect(searchInput).toHaveValue("");
		});
	});

	it("shows check mark for selected events", async () => {
		const user = userEvent.setup();
		render(
			<EventsCombobox
				selectedEvents={["prefect.flow-run.Completed"]}
				onToggleEvent={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			const selectedOption = screen.getByRole("option", {
				name: "prefect.flow-run.Completed",
			});
			const checkIcon = selectedOption.querySelector("svg");
			expect(checkIcon).toHaveClass("opacity-100");
		});
	});

	it("does not show check mark for unselected events", async () => {
		const user = userEvent.setup();
		render(
			<EventsCombobox
				selectedEvents={["prefect.flow-run.Completed"]}
				onToggleEvent={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button");
		await user.click(trigger);

		await waitFor(() => {
			const unselectedOption = screen.getByRole("option", {
				name: "prefect.flow-run.Failed",
			});
			const checkIcon = unselectedOption.querySelector("svg");
			expect(checkIcon).toHaveClass("opacity-0");
		});
	});
});
