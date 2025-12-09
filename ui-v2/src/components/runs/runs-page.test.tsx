import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { router } from "@/router";

const mockFlowRunsWithFilters = () => {
	server.use(
		http.post(buildApiUrl("/flow_runs/count"), () => {
			return HttpResponse.json(5);
		}),
		http.post(buildApiUrl("/flow_runs/paginate"), () => {
			return HttpResponse.json({
				results: [
					{
						id: "1",
						name: "test-flow-run-1",
						flow_id: "flow-1",
						state: { type: "COMPLETED", name: "Completed" },
						tags: ["tag1", "tag2"],
					},
					{
						id: "2",
						name: "test-flow-run-2",
						flow_id: "flow-2",
						state: { type: "FAILED", name: "Failed" },
						tags: [],
					},
				],
				count: 2,
				pages: 1,
				page: 1,
				limit: 10,
			});
		}),
		http.post(buildApiUrl("/flows/filter"), () => {
			return HttpResponse.json([
				{ id: "flow-1", name: "Test Flow 1", tags: [] },
				{ id: "flow-2", name: "Test Flow 2", tags: [] },
			]);
		}),
		http.post(buildApiUrl("/deployments/filter"), () => {
			return HttpResponse.json([
				{ id: "deployment-1", name: "Test Deployment 1", flow_id: "flow-1" },
				{ id: "deployment-2", name: "Test Deployment 2", flow_id: "flow-2" },
			]);
		}),
		http.post(buildApiUrl("/work_pools/filter"), () => {
			return HttpResponse.json([
				{ id: "pool-1", name: "Test Pool 1", type: "process" },
				{ id: "pool-2", name: "Test Pool 2", type: "kubernetes" },
			]);
		}),
		http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
			return HttpResponse.json({ "1": 3, "2": 0 });
		}),
	);
};

const renderRunsPage = async () => {
	const user = userEvent.setup();
	const result = await waitFor(() =>
		render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		}),
	);
	await user.click(screen.getByRole("link", { name: "Runs" }));
	return result;
};

describe("Runs page", () => {
	it("should render with empty state when no flow runs or task runs exist", async () => {
		await renderRunsPage();
		await waitFor(() => {
			expect(
				screen.getByText("Run a task or flow to get started"),
			).toBeVisible();
		});
	});

	it("should render tabs when flow runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(5);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [
						{
							id: "1",
							name: "test-flow-run-1",
							flow_id: "flow-1",
							state: { type: "COMPLETED", name: "Completed" },
							tags: [],
						},
					],
					count: 1,
					pages: 1,
					page: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([
					{ id: "flow-1", name: "Test Flow", tags: [] },
				]);
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "1": 0 });
			}),
		);

		await renderRunsPage();

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Flow Runs" })).toBeVisible();
			expect(screen.getByRole("tab", { name: "Task Runs" })).toBeVisible();
		});
	});

	it("should show flow runs list when flow runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(1);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [
						{
							id: "1",
							name: "test-flow-run-1",
							flow_id: "flow-1",
							state: { type: "COMPLETED", name: "Completed" },
							tags: [],
						},
					],
					count: 1,
					pages: 1,
					page: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([
					{ id: "flow-1", name: "Test Flow", tags: [] },
				]);
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "1": 0 });
			}),
		);

		await renderRunsPage();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run-1")).toBeVisible();
		});
	});

	it("should allow switching to task runs tab", async () => {
		const user = userEvent.setup();
		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(1);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [
						{
							id: "1",
							name: "test-flow-run-1",
							flow_id: "flow-1",
							state: { type: "COMPLETED", name: "Completed" },
							tags: [],
						},
					],
					count: 1,
					pages: 1,
					page: 1,
					limit: 10,
				});
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([
					{ id: "flow-1", name: "Test Flow", tags: [] },
				]);
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "1": 0 });
			}),
		);

		await renderRunsPage();

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Task Runs" })).toBeVisible();
		});

		await user.click(screen.getByRole("tab", { name: "Task Runs" }));

		await waitFor(() => {
			expect(screen.getByText("Task Runs tab coming soon")).toBeVisible();
		});
	});

	describe("Filter group", () => {
		it("should render filter group when flow runs exist", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByPlaceholderText("Search by run name")).toBeVisible();
			});
		});

		it("should render date range selector", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("Past 7 days")).toBeVisible();
			});
		});

		it("should render state filter", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("All run states")).toBeVisible();
			});
		});

		it("should render flow filter", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("All flows")).toBeVisible();
			});
		});

		it("should render deployment filter", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("All deployments")).toBeVisible();
			});
		});

		it("should render work pool filter", async () => {
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("All work pools")).toBeVisible();
			});
		});

		it("should allow typing in search input", async () => {
			const user = userEvent.setup();
			mockFlowRunsWithFilters();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByPlaceholderText("Search by run name")).toBeVisible();
			});

			const searchInput = screen.getByPlaceholderText("Search by run name");
			await user.type(searchInput, "test-search");

			expect(searchInput).toHaveValue("test-search");
		});
	});
});
