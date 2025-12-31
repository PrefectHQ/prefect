import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { EventsCombobox } from "./events-combobox";

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("EventsCombobox", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders with empty message when no events are selected", () => {
		render(
			<EventsCombobox
				selectedEvents={[]}
				onEventsChange={vi.fn()}
				emptyMessage="All events"
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("All events")).toBeVisible();
	});

	it("displays selected events", () => {
		render(
			<EventsCombobox
				selectedEvents={["prefect.flow-run.Completed"]}
				onEventsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("prefect.flow-run.Completed")).toBeVisible();
	});

	it("displays overflow indicator when more than 2 events are selected", () => {
		render(
			<EventsCombobox
				selectedEvents={[
					"prefect.flow-run.Completed",
					"prefect.flow-run.Failed",
					"prefect.flow-run.Running",
				]}
				onEventsChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("+1")).toBeVisible();
	});

	it("opens dropdown when clicked", async () => {
		const user = userEvent.setup();

		render(<EventsCombobox selectedEvents={[]} onEventsChange={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		await user.click(screen.getByRole("button"));

		expect(screen.getByPlaceholderText("Search events...")).toBeVisible();
	});

	it("can add and then deselect custom events", async () => {
		const user = userEvent.setup();
		const onEventsChange = vi.fn();

		render(
			<EventsCombobox selectedEvents={[]} onEventsChange={onEventsChange} />,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button"));
		await user.type(
			screen.getByPlaceholderText("Search events..."),
			"custom.event{Enter}",
		);

		expect(onEventsChange).toHaveBeenCalledWith(["custom.event"]);
	});

	it("can add custom events via Enter key", async () => {
		const user = userEvent.setup();
		const onEventsChange = vi.fn();

		render(
			<EventsCombobox selectedEvents={[]} onEventsChange={onEventsChange} />,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button"));
		await user.type(
			screen.getByPlaceholderText("Search events..."),
			"custom.event{Enter}",
		);

		expect(onEventsChange).toHaveBeenCalledWith(["custom.event"]);
	});

	it("shows custom empty message", () => {
		render(
			<EventsCombobox
				selectedEvents={[]}
				onEventsChange={vi.fn()}
				emptyMessage="Select events"
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Select events")).toBeVisible();
	});
});
