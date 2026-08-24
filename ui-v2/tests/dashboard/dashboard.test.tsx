import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { FlowRunsCountFilter } from "@/api/flow-runs";
import { createFakeFlowRun } from "@/mocks";
import { router } from "@/router";

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
				"https://docs.prefect.io/v3/get-started/quickstart#open-source",
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
			const countFilters: FlowRunsCountFilter[] = [];
			mockFlowRuns([createFakeFlowRun()]);
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), async ({ request }) => {
					countFilters.push((await request.json()) as FlowRunsCountFilter);
					return HttpResponse.json(5);
				}),
			);

			await renderDashboardPage();

			await waitFor(() => {
				expect(countFilters.length).toBeGreaterThan(0);
			});
			for (const filter of countFilters) {
				expect(filter.flow_runs?.expected_start_time?.after_).toBeTruthy();
				expect(filter.flow_runs?.expected_start_time?.before_).toBeTruthy();
			}
		});
	});
});
