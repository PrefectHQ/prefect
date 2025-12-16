import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { EventsCount, EventsCountFilter } from "@/api/events";
import { EventsTypeFilter } from "./events-type-filter";

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

const DEFAULT_FILTER: EventsCountFilter = {
	filter: {
		occurred: {
			since: "2024-01-01T00:00:00Z",
			until: "2024-01-31T23:59:59Z",
		},
		order: "ASC",
	},
	time_unit: "day",
	time_interval: 1,
};

describe("EventsTypeFilter", () => {
	it("shows 'All event types' when no event types are selected", async () => {
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("All event types")).toBeInTheDocument();
		});
	});

	it("shows selected event types in trigger", async () => {
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.*", "prefect.flow-run.*"]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText("prefect.*, prefect.flow-run.*"),
			).toBeInTheDocument();
		});
	});

	it("shows count when more than 2 event types are selected", async () => {
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[
					"prefect.*",
					"prefect.flow-run.*",
					"prefect.task-run.*",
				]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByText("+ 1")).toBeInTheDocument();
		});
	});

	it("opens dropdown and shows event type options with prefixes", async () => {
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /all event types/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.task-run.*" }),
			).toBeInTheDocument();
		});
	});

	it("selects an event type when clicking on it", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("prefect.*");
		await user.click(option);

		expect(onChange).toHaveBeenCalledWith(["prefect.*"]);
	});

	it("deselects an event type when clicking on an already selected item", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.*"]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("prefect.*");
		await user.click(option);

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("filters event types by search input", async () => {
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "flow-run");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.*" }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "prefect.task-run.*" }),
			).not.toBeInTheDocument();
		});
	});

	it("shows only 'All event types' option when search has no matches", async () => {
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const searchInput = screen.getByRole("combobox");
		await user.type(searchInput, "nonexistent");

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /all event types/i }),
			).toBeInTheDocument();
			expect(
				screen.queryByRole("option", { name: "prefect.*" }),
			).not.toBeInTheDocument();
		});
	});

	it("allows selecting multiple event types", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.*"]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("prefect.flow-run.*");
		await user.click(option);

		expect(onChange).toHaveBeenCalledWith(["prefect.*", "prefect.flow-run.*"]);
	});

	it("clears all selections when clicking 'All event types'", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.*", "prefect.flow-run.*"]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const allOption = await screen.findByRole("option", {
			name: /all event types/i,
		});
		await user.click(allOption);

		expect(onChange).toHaveBeenCalledWith([]);
	});

	it("has 'All event types' checkbox checked when no selections", async () => {
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={[]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		await waitFor(() => {
			const allOption = screen.getByRole("option", {
				name: /all event types/i,
			});
			const checkbox = allOption.querySelector('[role="checkbox"]');
			expect(checkbox).toHaveAttribute("data-state", "checked");
		});
	});

	it("shows all event types in dropdown even when some are selected", async () => {
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.flow-run.*"]}
				onEventTypesChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		await waitFor(() => {
			expect(
				screen.getByRole("option", { name: /all event types/i }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.flow-run.*" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("option", { name: "prefect.task-run.*" }),
			).toBeInTheDocument();
		});
	});

	it("allows adding additional event types to existing selection", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.flow-run.*"]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("prefect.task-run.*");
		await user.click(option);

		expect(onChange).toHaveBeenCalledWith([
			"prefect.flow-run.*",
			"prefect.task-run.*",
		]);
	});

	it("allows removing event types from selection while keeping others", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={["prefect.flow-run.*", "prefect.task-run.*"]}
				onEventTypesChange={onChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const trigger = await screen.findByRole("button", {
			name: /filter by event type/i,
		});
		await user.click(trigger);

		const listbox = await screen.findByRole("listbox");
		const option = await within(listbox).findByText("prefect.flow-run.*");
		await user.click(option);

		expect(onChange).toHaveBeenCalledWith(["prefect.task-run.*"]);
	});
});
