import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { format } from "date-fns";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FlowRunsCountFilter } from "@/api/flow-runs";
import { createFakeFlowRun } from "@/mocks";
import { createAppRouter, router } from "@/router";

const mockFlowRuns = (flowRuns: unknown[]) =>
	server.use(
		http.post(buildApiUrl("/flow_runs/filter"), () =>
			HttpResponse.json(flowRuns),
		),
	);

const renderDashboardPage = async () => {
	const user = userEvent.setup();
	const view = render(<RouterProvider router={router} />, {
		wrapper: createWrapper(),
	});
	await user.click(await screen.findByRole("link", { name: "Dashboard" }));
	return view;
};

describe("Dashboard page", () => {
	describe("Date range URLs", () => {
		beforeEach(() => {
			vi.useFakeTimers({ toFake: ["Date"] });
			vi.setSystemTime(new Date("2024-06-01T12:00:00.000Z"));
		});

		afterEach(() => {
			vi.useRealTimers();
		});

		it.each([
			{
				url: "/dashboard?seconds=-3600",
				label: "Past hour",
				from: "2024-06-01T11:00:00.000Z",
				to: "2024-06-01T12:00:00.000Z",
			},
			{
				url: "/dashboard?seconds=3600",
				label: "Next hour",
				from: "2024-06-01T12:00:00.000Z",
				to: "2024-06-01T13:00:00.000Z",
			},
			{
				url: "/dashboard?seconds=-3600&from=2020-01-01T00:00:00.000Z&to=2020-01-01T01:00:00.000Z",
				from: "2020-01-01T00:00:00.000Z",
				to: "2020-01-01T01:00:00.000Z",
			},
			{
				url: "/dashboard?rangeType=range&start=2020-01-01T00:00:00.000Z&end=2020-01-01T01:00:00.000Z",
				from: "2020-01-01T00:00:00.000Z",
				to: "2020-01-01T01:00:00.000Z",
			},
		])(
			"keeps the selector and queried range aligned for $url",
			async ({ url, label, from, to }) => {
				const ranges: unknown[] = [];
				mockFlowRuns([createFakeFlowRun()]);
				server.use(
					http.post(buildApiUrl("/flow_runs/count"), async ({ request }) => {
						const filter = (await request.json()) as FlowRunsCountFilter;
						ranges.push(filter.flow_runs?.expected_start_time);
						return HttpResponse.json(5);
					}),
				);

				const queryClient = new QueryClient({
					defaultOptions: { queries: { retry: false } },
				});
				const dashboardRouter = createAppRouter({
					queryClient,
					history: createMemoryHistory({ initialEntries: [url] }),
				});
				render(<RouterProvider router={dashboardRouter} />, {
					wrapper: createWrapper({ queryClient }),
				});

				const expectedLabel =
					label ??
					`${format(new Date(from), "MMM do, yyyy 'at' hh:mm a")} - ${format(new Date(to), "MMM do, yyyy 'at' hh:mm a")}`;
				expect(
					await screen.findByRole("button", { name: expectedLabel }),
				).toBeVisible();
				await waitFor(() => expect(ranges.length).toBeGreaterThan(0));
				for (const range of ranges) {
					expect(range).toEqual({ after_: from, before_: to });
				}
			},
		);
	});

	describe("Empty state", () => {
		it("should render empty state when there are no flow runs", async () => {
			mockFlowRuns([]);

			await renderDashboardPage();

			expect(
				screen.getByText("Run a task or flow to get started"),
			).toBeVisible();
			expect(
				screen.getByText(
					"Runs store the state history for each execution of a task or flow.",
				),
			).toBeVisible();
			expect(screen.getByRole("link", { name: "View Docs" })).toBeVisible();
		});

		it("should hide filters when empty state is shown", async () => {
			mockFlowRuns([]);

			await renderDashboardPage();

			expect(screen.queryByLabelText("Hide subflows")).not.toBeInTheDocument();
			expect(screen.queryByText("All tags")).not.toBeInTheDocument();
		});

		it("should link to the correct docs URL", async () => {
			mockFlowRuns([]);

			await renderDashboardPage();

			const docsLink = screen.getByRole("link", { name: "View Docs" });
			expect(docsLink).toHaveAttribute(
				"href",
				"https://www.prefect.io/docs/v3/get-started/quickstart#open-source",
			);
		});
	});

	describe("With flow runs", () => {
		it("should not render empty state when flow runs exist", async () => {
			mockFlowRuns([createFakeFlowRun()]);

			await renderDashboardPage();

			await waitFor(() => {
				expect(
					screen.queryByText("Run a task or flow to get started"),
				).not.toBeInTheDocument();
			});
		});

		it("should show filters when flow runs exist", async () => {
			mockFlowRuns([createFakeFlowRun()]);

			await renderDashboardPage();

			await waitFor(() => {
				expect(screen.getByLabelText("Hide subflows")).toBeVisible();
			});
		});

		it("should bound every flow run count by the dashboard time window", async () => {
			const unboundedFilters: FlowRunsCountFilter[] = [];
			let countRequests = 0;
			mockFlowRuns([createFakeFlowRun()]);
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), async ({ request }) => {
					const filter = (await request.json()) as FlowRunsCountFilter;
					countRequests += 1;
					const range = filter.flow_runs?.expected_start_time;
					if (!range?.after_ || !range?.before_) {
						unboundedFilters.push(filter);
					}
					return HttpResponse.json(5);
				}),
			);

			await renderDashboardPage();

			await waitFor(() => {
				expect(screen.getByLabelText("Hide subflows")).toBeVisible();
				expect(countRequests).toBeGreaterThan(0);
			});

			expect(unboundedFilters).toEqual([]);
		});
	});
});
