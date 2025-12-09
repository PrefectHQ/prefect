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
});
