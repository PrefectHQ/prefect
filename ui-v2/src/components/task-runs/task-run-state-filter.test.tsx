import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createContext, type ReactNode, useContext } from "react";
import { describe, expect, it, vi } from "vitest";
import { TaskRunStateFilter } from "./task-run-state-filter";

const TestChildrenContext = createContext<ReactNode>(null);

function RenderTestChildren() {
	const children = useContext(TestChildrenContext);
	return (
		<>
			{children}
			<Outlet />
		</>
	);
}

const renderWithProviders = async (ui: ReactNode) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const rootRoute = createRootRoute({
		component: RenderTestChildren,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	const result = render(
		<QueryClientProvider client={queryClient}>
			<TestChildrenContext.Provider value={ui}>
				<RouterProvider router={router} />
			</TestChildrenContext.Provider>
		</QueryClientProvider>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

describe("TaskRunStateFilter", () => {
	it("renders with 'All run states' when no filters selected", async () => {
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set()}
				onSelectFilter={onSelectFilter}
			/>,
		);

		expect(screen.getByText("All run states")).toBeInTheDocument();
	});

	it("opens dropdown when clicked", async () => {
		const user = userEvent.setup();
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set()}
				onSelectFilter={onSelectFilter}
			/>,
		);

		await user.click(screen.getByText("All run states"));

		await waitFor(() => {
			expect(screen.getByText("All except scheduled")).toBeInTheDocument();
		});
	});

	it("shows state options in dropdown", async () => {
		const user = userEvent.setup();
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set()}
				onSelectFilter={onSelectFilter}
			/>,
		);

		await user.click(screen.getByText("All run states"));

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
			expect(screen.getByText("Failed")).toBeInTheDocument();
			expect(screen.getByText("Running")).toBeInTheDocument();
			expect(screen.getByText("Scheduled")).toBeInTheDocument();
		});
	});

	it("calls onSelectFilter when a state is selected", async () => {
		const user = userEvent.setup();
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set()}
				onSelectFilter={onSelectFilter}
			/>,
		);

		await user.click(screen.getByText("All run states"));

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});

		await user.click(screen.getByRole("menuitem", { name: "Completed" }));

		expect(onSelectFilter).toHaveBeenCalledWith(new Set(["Completed"]));
	});

	it("displays selected state badges when filters are selected", async () => {
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set(["Completed"])}
				onSelectFilter={onSelectFilter}
			/>,
		);

		// Should show the Completed badge instead of "All run states"
		expect(screen.queryByText("All run states")).not.toBeInTheDocument();
	});

	it("calls onSelectFilter with empty set when 'All run states' is selected", async () => {
		const user = userEvent.setup();
		const onSelectFilter = vi.fn();

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={new Set(["Completed"])}
				onSelectFilter={onSelectFilter}
			/>,
		);

		// Open dropdown by clicking the button
		const button = screen.getByRole("button");
		await user.click(button);

		await waitFor(() => {
			expect(
				screen.getByRole("menuitem", { name: "All run states" }),
			).toBeInTheDocument();
		});

		await user.click(screen.getByRole("menuitem", { name: "All run states" }));

		expect(onSelectFilter).toHaveBeenCalledWith(new Set());
	});

	it("shows 'All except scheduled' when all states except Scheduled are selected", async () => {
		const onSelectFilter = vi.fn();
		// All states except Scheduled
		const allExceptScheduled = new Set([
			"Late",
			"Resuming",
			"AwaitingRetry",
			"AwaitingConcurrencySlot",
			"Pending",
			"Paused",
			"Suspended",
			"Running",
			"Retrying",
			"Completed",
			"Cached",
			"Cancelled",
			"Cancelling",
			"Crashed",
			"Failed",
			"TimedOut",
		]);

		await renderWithProviders(
			<TaskRunStateFilter
				selectedFilters={allExceptScheduled}
				onSelectFilter={onSelectFilter}
			/>,
		);

		expect(screen.getByText("All except scheduled")).toBeInTheDocument();
	});
});
