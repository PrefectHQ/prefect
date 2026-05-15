import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DeploymentWithFlow } from "@/api/deployments";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeFlowRun,
	createFakeFlowRunWithDeploymentAndFlow,
} from "@/mocks/create-fake-flow-run";
import { DeploymentsDataTable, type DeploymentsDataTableProps } from ".";

describe("DeploymentsDataTable", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), async ({ request }) => {
				const { limit } = (await request.json()) as { limit: number };

				return HttpResponse.json(
					Array.from({ length: limit }, createFakeFlowRunWithDeploymentAndFlow),
				);
			}),
		);
	});
	const mockDeployment: DeploymentWithFlow = {
		id: "test-id",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
		name: "Test Deployment",
		flow_id: "flow-id",
		paused: false,
		status: "READY",
		enforce_parameter_schema: true,
		tags: ["tag1", "tag2"],
		flow: {
			id: "flow-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			name: "test-flow",
		},
	};

	const defaultProps = {
		deployments: [mockDeployment],
		currentDeploymentsCount: 1,
		pageCount: 5,
		pagination: {
			pageSize: 10,
			pageIndex: 2,
		},
		sort: "NAME_ASC" as const,
		columnFilters: [],
		onPaginationChange: vi.fn(),
		onSortChange: vi.fn(),
		onColumnFiltersChange: vi.fn(),
	};

	// Wraps component in test with a Tanstack router provider
	const DeploymentsDataTableRouter = (props: DeploymentsDataTableProps) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<DeploymentsDataTable {...props} />
				</>
			),
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

	const renderDeploymentsDataTableRouter = (
		props: DeploymentsDataTableProps,
	) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<DeploymentsDataTable {...props} />
				</>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/deployments"],
			}),
			context: { queryClient: new QueryClient() },
		});

		return [
			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			}),
			router,
		] as const;
	};

	it("renders deployment name and flow name", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);
		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
	});

	it("renders status badge", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Ready")).toBeInTheDocument();
	});

	it("renders tags", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	it("renders with empty deployments array", async () => {
		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter {...defaultProps} deployments={[]} />,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(screen.queryByText("No Results")).not.toBeInTheDocument();
	});

	it("renders multiple deployments", async () => {
		const multipleDeployments = [
			mockDeployment,
			{
				...mockDeployment,
				id: "test-id-2",
				created: new Date().toISOString(),
				updated: new Date().toISOString(),
				name: "Second Deployment",
				flow: {
					id: "flow-id-2",
					created: new Date().toISOString(),
					updated: new Date().toISOString(),
					name: "second-flow",
				},
			},
		];

		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter
					{...defaultProps}
					deployments={multipleDeployments}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(screen.getByText("Test Deployment")).toBeInTheDocument();
		expect(screen.getByText("Second Deployment")).toBeInTheDocument();
		expect(screen.getByText("test-flow")).toBeInTheDocument();
		expect(screen.getByText("second-flow")).toBeInTheDocument();
		expect(screen.getByText("1 Deployment")).toBeInTheDocument();
	});

	it("calls onQuickRun when quick run action is clicked", async () => {
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				return HttpResponse.json(createFakeFlowRun({ name: "new-flow-run" }));
			}),
		);

		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const quickRunButton = screen.getByRole("menuitem", { name: "Quick Run" });
		await userEvent.click(quickRunButton);

		await waitFor(() => {
			expect(screen.getByText("new-flow-run")).toBeVisible();
			expect(screen.getByRole("button", { name: "View run" })).toBeVisible();
		});
	});

	it("has an action menu item that links to create a custom run", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		expect(screen.getByRole("menuitem", { name: "Custom Run" })).toBeVisible();
		expect(screen.getByRole("link", { name: /custom run/i })).toBeVisible();
	});

	it("has an action menu item that links to edit deployment", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		expect(screen.getByRole("menuitem", { name: "Edit" })).toBeVisible();
		expect(screen.getByRole("link", { name: /edit/i })).toBeVisible();
	});

	it("handles deletion", async () => {
		const [, router] = renderDeploymentsDataTableRouter(defaultProps);

		await screen.findByRole("button", { name: "Open menu" });

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const deleteButton = screen.getByRole("menuitem", { name: "Delete" });
		await userEvent.click(deleteButton);

		expect(router.state.location.pathname).toBe("/deployments");

		const confirmDeleteButton = screen.getByRole("button", {
			name: "Delete",
		});
		await userEvent.click(confirmDeleteButton);

		expect(screen.getByText("Deployment deleted")).toBeInTheDocument();
	});

	it("has an action menu item that links to duplicate deployment", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		expect(screen.getByRole("menuitem", { name: "Duplicate" })).toBeVisible();
		expect(screen.getByRole("link", { name: /duplicate/i })).toBeVisible();
	});

	it("calls onPaginationChange when pagination buttons are clicked", async () => {
		const onPaginationChange = vi.fn();
		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter
					{...defaultProps}
					onPaginationChange={onPaginationChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		await userEvent.click(
			screen.getByRole("button", { name: "Go to next page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 3,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to previous page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 1,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to first page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 0,
			pageSize: 10,
		});

		await userEvent.click(
			screen.getByRole("button", { name: "Go to last page" }),
		);

		expect(onPaginationChange).toHaveBeenCalledWith({
			pageIndex: 4,
			pageSize: 10,
		});
	});

	it("calls onSortChange when sort is changed", async () => {
		const user = userEvent.setup();

		mockPointerEvents();
		const onSortChange = vi.fn();
		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter
					{...defaultProps}
					onSortChange={onSortChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		const select = screen.getByRole("combobox", {
			name: "Deployment sort order",
		});
		await userEvent.click(select);
		await userEvent.click(screen.getByText("Created"));

		expect(onSortChange).toHaveBeenCalledWith("CREATED_DESC");

		await user.click(select);
		await user.click(screen.getByText("Updated"));
		expect(onSortChange).toHaveBeenCalledWith("UPDATED_DESC");

		await user.click(select);
		await user.click(screen.getByText("Z to A"));
		expect(onSortChange).toHaveBeenCalledWith("NAME_DESC");
	});

	it("calls onColumnFiltersChange on deployment name search", async () => {
		const user = userEvent.setup();

		const onColumnFiltersChange = vi.fn();
		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter
					{...defaultProps}
					columnFilters={[{ id: "flowOrDeploymentName", value: "start value" }]}
					onColumnFiltersChange={onColumnFiltersChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		// Clear any initial calls from mounting
		onColumnFiltersChange.mockClear();

		const nameSearchInput = screen.getByPlaceholderText("Search deployments");
		expect(nameSearchInput).toHaveValue("start value");

		await user.clear(nameSearchInput);
		await user.type(nameSearchInput, "my-deployment");

		// Wait for the debounced callback to be called (SearchInput has 200ms debounce)
		await waitFor(() => {
			expect(onColumnFiltersChange).toHaveBeenCalledWith([
				{ id: "flowOrDeploymentName", value: "my-deployment" },
			]);
		});
	});

	it("renders rows with cursor-pointer class for onRowClick", async () => {
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		// Data rows should have cursor-pointer class since onRowClick is wired
		const rows = screen.getAllByRole("row");
		// First row is the header; data rows start at index 1
		const dataRow = rows[1];
		expect(dataRow).toHaveClass("cursor-pointer");
	});

	describe("column resizing", () => {
		const STORAGE_KEY = "deployments-table-column-sizing";

		const installLocalStorageBacking = () => {
			const store = new Map<string, string>();
			vi.spyOn(localStorage, "getItem").mockImplementation(
				(key) => store.get(key) ?? null,
			);
			vi.spyOn(localStorage, "setItem").mockImplementation((key, value) => {
				store.set(key, value);
			});
			vi.spyOn(localStorage, "removeItem").mockImplementation((key) => {
				store.delete(key);
			});
			return store;
		};

		afterEach(() => {
			vi.restoreAllMocks();
		});

		it("renders a draggable resize handle for the Deployment column", async () => {
			installLocalStorageBacking();

			await waitFor(() =>
				render(<DeploymentsDataTableRouter {...defaultProps} />, {
					wrapper: createWrapper(),
				}),
			);

			expect(
				screen.getByTestId("column-resize-handle-name"),
			).toBeInTheDocument();
		});

		it("does not render a resize handle for the actions column", async () => {
			installLocalStorageBacking();

			await waitFor(() =>
				render(<DeploymentsDataTableRouter {...defaultProps} />, {
					wrapper: createWrapper(),
				}),
			);

			expect(
				screen.queryByTestId("column-resize-handle-actions"),
			).not.toBeInTheDocument();
		});

		it("persists resized column widths to localStorage", async () => {
			const store = installLocalStorageBacking();

			await waitFor(() =>
				render(<DeploymentsDataTableRouter {...defaultProps} />, {
					wrapper: createWrapper(),
				}),
			);

			const handle = screen.getByTestId("column-resize-handle-name");

			fireEvent.mouseDown(handle, { clientX: 200 });
			fireEvent.mouseMove(document, { clientX: 360 });
			fireEvent.mouseUp(document, { clientX: 360 });

			await waitFor(() => {
				const stored = store.get(STORAGE_KEY);
				expect(stored).toBeDefined();
				const parsed = JSON.parse(stored ?? "{}") as Record<string, number>;
				expect(parsed.name).toBe(360);
			});
		});

		it("restores resized column widths from localStorage on mount", async () => {
			const store = installLocalStorageBacking();
			store.set(STORAGE_KEY, JSON.stringify({ name: 420 }));

			await waitFor(() =>
				render(<DeploymentsDataTableRouter {...defaultProps} />, {
					wrapper: createWrapper(),
				}),
			);

			const nameHeader = screen.getByRole("columnheader", {
				name: "Deployment",
			});
			expect(nameHeader).toHaveStyle({ width: "420px" });
		});
	});

	it("calls onColumnFiltersChange on tags search", async () => {
		const user = userEvent.setup();

		const onColumnFiltersChange = vi.fn();
		await waitFor(() =>
			render(
				<DeploymentsDataTableRouter
					{...defaultProps}
					columnFilters={[{ id: "tags", value: ["tag3"] }]}
					onColumnFiltersChange={onColumnFiltersChange}
				/>,
				{ wrapper: createWrapper() },
			),
		);

		// Clear any initial calls from mounting
		onColumnFiltersChange.mockClear();

		const tagsSearchInput = screen.getByPlaceholderText("Filter by tags");
		expect(await screen.findByText("tag3")).toBeVisible();

		await user.type(tagsSearchInput, "tag4");
		await user.keyboard("{enter}");

		expect(onColumnFiltersChange).toHaveBeenCalledWith([
			{ id: "tags", value: ["tag3", "tag4"] },
		]);
	});
});
