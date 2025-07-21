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
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DeploymentWithFlow } from "@/api/deployments";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeFlowRun,
	createFakeFlowRunWithDeploymentAndFlow,
} from "@/mocks/create-fake-flow-run";
import { DeploymentsDataTable, type DeploymentsDataTableProps } from ".";

describe("DeploymentsDataTable", () => {
	beforeEach(() => {
		// Mocks away getRouteApi dependency in `useDeleteDeploymentConfirmationDialog`
		// @ts-expect-error Ignoring error until @tanstack/react-router has better testing documentation. Ref: https://vitest.dev/api/vi.html#vi-mock
		vi.mock(import("@tanstack/react-router"), async (importOriginal) => {
			const mod = await importOriginal();
			return {
				...mod,
				getRouteApi: () => ({
					useNavigate: vi.fn,
				}),
			};
		});

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
		await waitFor(() =>
			render(<DeploymentsDataTableRouter {...defaultProps} />, {
				wrapper: createWrapper(),
			}),
		);

		await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
		const deleteButton = screen.getByRole("menuitem", { name: "Delete" });
		await userEvent.click(deleteButton);

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

		expect(onColumnFiltersChange).toHaveBeenCalledWith([
			{ id: "flowOrDeploymentName", value: "my-deployment" },
		]);
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
