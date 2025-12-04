import { RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { router } from "@/router";

const renderDashboardPage = async () => {
	const user = userEvent.setup();
	const result = await waitFor(() =>
		render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		}),
	);
	await user.click(screen.getByRole("link", { name: "Dashboard" }));
	return result;
};

describe("Dashboard page", () => {
	describe("Empty state", () => {
		it("should render empty state when there are no flow runs", async () => {
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			);

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
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			);

			await renderDashboardPage();

			expect(screen.queryByLabelText("Hide subflows")).not.toBeInTheDocument();
			expect(screen.queryByText("All tags")).not.toBeInTheDocument();
		});

		it("should link to the correct docs URL", async () => {
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			);

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
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(5);
				}),
			);

			await renderDashboardPage();

			await waitFor(() => {
				expect(
					screen.queryByText("Run a task or flow to get started"),
				).not.toBeInTheDocument();
			});
		});

		it("should show filters when flow runs exist", async () => {
			server.use(
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(5);
				}),
			);

			await renderDashboardPage();

			await waitFor(() => {
				expect(screen.getByLabelText("Hide subflows")).toBeVisible();
			});
		});
	});
});
