import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Flow } from "@/api/flows";
import { createFakeFlow } from "@/mocks/create-fake-flow";
import FlowsTable from "./data-table";

describe("FlowsTable", () => {
	const mockFlow = createFakeFlow({ name: "Test Flow" });

	const defaultProps = {
		flows: [mockFlow],
		count: 1,
		pageCount: 1,
		pagination: {
			pageSize: 10,
			pageIndex: 0,
		},
		sort: "NAME_ASC" as const,
		columnFilters: [],
		onPaginationChange: vi.fn(),
		onSortChange: vi.fn(),
		onColumnFiltersChange: vi.fn(),
	};

	// Wraps component in test with a Tanstack router provider
	const FlowsTableRouter = (props: Parameters<typeof FlowsTable>[0]) => {
		const rootRoute = createRootRoute({
			component: () => <FlowsTable {...props} />,
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: { queryClient: new QueryClient() },
		});
		return <RouterProvider router={router} />;
	};

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => HttpResponse.json([])),
			http.post(buildApiUrl("/ui/flows/next-runs"), () =>
				HttpResponse.json({}),
			),
			http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
				HttpResponse.json({}),
			),
		);
	});

	it("renders flow name and count", async () => {
		await waitFor(() =>
			render(<FlowsTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Test Flow")).toBeInTheDocument();
		expect(screen.getByText("1 Flow")).toBeInTheDocument();
	});

	it("keeps the search input visible and allows clearing filters when there are no matches", async () => {
		const user = userEvent.setup();
		const onClearFilters = vi.fn();

		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					flows={[]}
					count={0}
					pageCount={0}
					columnFilters={[{ id: "name", value: "zzz" }]}
					onClearFilters={onClearFilters}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByPlaceholderText("Flow names")).toBeInTheDocument();
		expect(screen.getByText("No flows match your filters")).toBeInTheDocument();

		await user.click(screen.getByRole("button", { name: "Clear filters" }));
		expect(onClearFilters).toHaveBeenCalled();
	});

	it("keeps the table visible while filtered results are reloading", async () => {
		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					flows={[]}
					count={0}
					isPlaceholderData={true}
					onClearFilters={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByPlaceholderText("Flow names")).toBeInTheDocument();
		expect(
			screen.queryByText("No flows match your filters"),
		).not.toBeInTheDocument();
	});

	it("does not show the filtered empty state while the first page is pending", async () => {
		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					flows={[]}
					count={0}
					isPending={true}
					onClearFilters={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(
			screen.queryByText("No flows match your filters"),
		).not.toBeInTheDocument();
	});

	it("calls onColumnFiltersChange on flow name search", async () => {
		const user = userEvent.setup();
		const onColumnFiltersChange = vi.fn();

		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					onColumnFiltersChange={onColumnFiltersChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		onColumnFiltersChange.mockClear();

		const nameSearchInput = screen.getByPlaceholderText("Flow names");
		await user.type(nameSearchInput, "my-flow");

		// Wait for the debounced callback to be called (SearchInput has 200ms debounce)
		await waitFor(() => {
			expect(onColumnFiltersChange).toHaveBeenCalledWith([
				{ id: "name", value: "my-flow" },
			]);
		});
	});

	it("deletes the correct flows when selected across pages", async () => {
		const user = userEvent.setup();
		const deletedIds: string[] = [];
		server.use(
			http.delete(buildApiUrl("/flows/:id"), ({ params }) => {
				deletedIds.push(params.id as string);
				return HttpResponse.json({ status: 204 });
			}),
		);

		const flows = Array.from({ length: 20 }, () => createFakeFlow());

		// Owns pagination state so navigating updates the rows fed to the table,
		// like the route does with URL-driven pagination
		const PaginatedTable = () => {
			const [pagination, setPagination] = useState({
				pageIndex: 0,
				pageSize: 10,
			});
			const pageFlows = flows.slice(
				pagination.pageIndex * pagination.pageSize,
				(pagination.pageIndex + 1) * pagination.pageSize,
			);
			return (
				<FlowsTable
					{...defaultProps}
					flows={pageFlows}
					count={20}
					pageCount={2}
					pagination={pagination}
					onPaginationChange={setPagination}
				/>
			);
		};

		const router = createRouter({
			routeTree: createRootRoute({ component: PaginatedTable }),
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient: new QueryClient() },
		});

		await waitFor(() =>
			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			}),
		);

		await user.click(
			screen.getAllByRole("checkbox", { name: "Select row" })[0],
		);
		expect(screen.getByText("1 selected")).toBeInTheDocument();

		await user.click(screen.getByRole("button", { name: "Go to next page" }));

		await user.click(
			screen.getAllByRole("checkbox", { name: "Select row" })[0],
		);
		expect(screen.getByText("2 selected")).toBeInTheDocument();

		await user.click(
			screen.getByRole("button", { name: "Delete selected flows" }),
		);

		await waitFor(() => {
			expect(deletedIds.sort()).toEqual([flows[0].id, flows[10].id].sort());
		});
		await waitFor(() => {
			expect(screen.queryByText("2 selected")).not.toBeInTheDocument();
		});
	});

	it("shows the error state with retry while keeping the toolbar mounted", async () => {
		const user = userEvent.setup();
		const onRetry = vi.fn();

		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					flows={[]}
					count={0}
					onClearFilters={vi.fn()}
					error={{
						type: "server-error",
						message: "Prefect server error",
						statusCode: 500,
					}}
					onRetry={onRetry}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		expect(screen.getByPlaceholderText("Flow names")).toBeInTheDocument();
		expect(screen.getByText("Prefect server error")).toBeVisible();
		expect(
			screen.queryByText("No flows match your filters"),
		).not.toBeInTheDocument();

		await user.click(screen.getByRole("button", { name: "Retry" }));
		expect(onRetry).toHaveBeenCalled();
	});

	it("calls onPaginationChange when pagination buttons are clicked", async () => {
		const onPaginationChange = vi.fn();
		const flows: Flow[] = Array.from({ length: 10 }, () => createFakeFlow());

		await waitFor(() =>
			render(
				<FlowsTableRouter
					{...defaultProps}
					flows={flows}
					count={20}
					pageCount={2}
					onPaginationChange={onPaginationChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		await userEvent.click(
			screen.getByRole("button", { name: "Go to next page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 1,
			pageSize: 10,
		});
	});
});
