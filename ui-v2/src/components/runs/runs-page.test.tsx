import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { router } from "@/router";

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

const setupFlowRunsHandlers = (
	flowRuns = [
		{
			id: "1",
			name: "test-flow-run-1",
			flow_id: "flow-1",
			state: { type: "COMPLETED", name: "Completed" },
			tags: [],
		},
		{
			id: "2",
			name: "test-flow-run-2",
			flow_id: "flow-1",
			state: { type: "RUNNING", name: "Running" },
			tags: [],
		},
	],
) => {
	server.use(
		http.post(buildApiUrl("/flow_runs/count"), () => {
			return HttpResponse.json(flowRuns.length);
		}),
		http.post(buildApiUrl("/flow_runs/paginate"), () => {
			return HttpResponse.json({
				results: flowRuns,
				count: flowRuns.length,
				pages: 1,
				page: 1,
				limit: 10,
			});
		}),
		http.post(buildApiUrl("/flows/filter"), () => {
			return HttpResponse.json([{ id: "flow-1", name: "Test Flow", tags: [] }]);
		}),
		http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
			return HttpResponse.json({ "1": 0, "2": 0 });
		}),
		http.delete(buildApiUrl("/flow_runs/:id"), () => {
			return new HttpResponse(null, { status: 204 });
		}),
	);
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

	it("should allow switching to task runs tab and show task runs UI", async () => {
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
			http.post(buildApiUrl("/task_runs/paginate"), () => {
				return HttpResponse.json({
					results: [
						{
							id: "task-1",
							name: "test-task-run-1",
							flow_run_id: null,
							task_key: "test-task",
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
		);

		await renderRunsPage();

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Task Runs" })).toBeVisible();
		});

		await user.click(screen.getByRole("tab", { name: "Task Runs" }));

		await waitFor(() => {
			// Should show task runs search input
			expect(
				screen.getByPlaceholderText("Search by task run name"),
			).toBeVisible();
		});
	});

	describe("Search functionality", () => {
		it("should render search input when flow runs exist", async () => {
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText("Search by flow run name"),
				).toBeVisible();
			});
		});

		it("should allow typing in search input", async () => {
			const user = userEvent.setup();
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(
					screen.getByPlaceholderText("Search by flow run name"),
				).toBeVisible();
			});

			const searchInput = screen.getByPlaceholderText(
				"Search by flow run name",
			);
			await user.type(searchInput, "test-search");

			expect(searchInput).toHaveValue("test-search");
		});

		it("should have correct aria-label for accessibility", async () => {
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByLabelText("Search by flow run name")).toBeVisible();
			});
		});
	});

	describe("Row selection", () => {
		it("should show select-all checkbox when flow runs exist", async () => {
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: "Toggle all" }),
				).toBeVisible();
			});
		});

		it("should select individual flow run when checkbox is clicked", async () => {
			const user = userEvent.setup();
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("test-flow-run-1")).toBeVisible();
			});

			// Find and click the first flow run's checkbox
			const checkboxes = screen.getAllByRole("checkbox");
			// First checkbox is the "Toggle all", subsequent ones are for individual rows
			const firstRowCheckbox = checkboxes[1];
			await user.click(firstRowCheckbox);

			await waitFor(() => {
				expect(screen.getByText("1 selected")).toBeVisible();
			});
		});

		it("should show delete button when rows are selected", async () => {
			const user = userEvent.setup();
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("test-flow-run-1")).toBeVisible();
			});

			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[1]);

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: "Delete rows" }),
				).toBeVisible();
			});
		});

		it("should select all rows when toggle all checkbox is clicked", async () => {
			const user = userEvent.setup();
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(
					screen.getByRole("checkbox", { name: "Toggle all" }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("checkbox", { name: "Toggle all" }));

			await waitFor(() => {
				expect(screen.getByText("2 selected")).toBeVisible();
			});
		});

		it("should show confirmation dialog when delete button is clicked", async () => {
			const user = userEvent.setup();
			setupFlowRunsHandlers();
			await renderRunsPage();

			await waitFor(() => {
				expect(screen.getByText("test-flow-run-1")).toBeVisible();
			});

			const checkboxes = screen.getAllByRole("checkbox");
			await user.click(checkboxes[1]);

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: "Delete rows" }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("button", { name: "Delete rows" }));

			await waitFor(() => {
				expect(screen.getByText("Delete Flow Runs")).toBeVisible();
				expect(
					screen.getByText(
						"Are you sure you want to delete selected flow runs?",
					),
				).toBeVisible();
			});
		});
	});
});
