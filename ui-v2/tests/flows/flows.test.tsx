import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeFlow } from "@/mocks/create-fake-flow";
import { createAppRouter } from "@/router";

const flows = [
	createFakeFlow({ name: "alpha" }),
	createFakeFlow({ name: "beta" }),
];

type PaginateBody = {
	flows?: { name?: { like_?: string } };
	page?: number;
	limit?: number;
};

const renderFlowsPage = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});
	const router = createAppRouter({
		queryClient,
		history: createMemoryHistory({ initialEntries: ["/flows"] }),
	});
	render(<RouterProvider router={router} />, {
		wrapper: createWrapper({ queryClient }),
	});
	return { router };
};

describe("Flows page", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flows/count"), () =>
				HttpResponse.json(flows.length),
			),
			http.post(buildApiUrl("/flows/paginate"), async ({ request }) => {
				const body = (await request.json()) as PaginateBody;
				const like = body.flows?.name?.like_?.toLowerCase();
				const limit = body.limit ?? 10;
				const results = like
					? flows.filter((flow) => flow.name.toLowerCase().includes(like))
					: flows;
				return HttpResponse.json({
					results,
					count: results.length,
					limit,
					pages: Math.ceil(results.length / limit),
					page: body.page ?? 1,
				});
			}),
		);
	});

	it("keeps the search input mounted and focused while typing", async () => {
		// delay > SearchInput's 200ms debounce so each keystroke commits to the URL
		const user = userEvent.setup({ delay: 300 });
		const { router } = renderFlowsPage();

		const searchInput = await screen.findByPlaceholderText("Flow names");
		await user.type(searchInput, "alpha");

		await waitFor(() => {
			expect(router.state.location.search).toMatchObject({ name: "alpha" });
		});

		expect(searchInput).toHaveFocus();
		expect(searchInput).toHaveValue("alpha");
		expect(await screen.findByText("alpha")).toBeVisible();
	});

	it("keeps the search input mounted and focused when a search returns no matches", async () => {
		const user = userEvent.setup({ delay: 300 });
		renderFlowsPage();

		const searchInput = await screen.findByPlaceholderText("Flow names");
		await user.type(searchInput, "zzz");

		expect(
			await screen.findByText("No flows match your filters"),
		).toBeVisible();
		expect(screen.getByPlaceholderText("Flow names")).toHaveFocus();
		expect(screen.getByPlaceholderText("Flow names")).toHaveValue("zzz");

		await user.click(screen.getByRole("button", { name: "Clear filters" }));
		await waitFor(() => {
			expect(screen.getByPlaceholderText("Flow names")).toHaveValue("");
		});
	});

	it("shows the error state instead of onboarding when pagination fails on an empty account", async () => {
		server.use(
			http.post(buildApiUrl("/flows/count"), () => HttpResponse.json(0)),
			http.post(buildApiUrl("/flows/paginate"), () =>
				HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 }),
			),
		);
		renderFlowsPage();

		expect(await screen.findByText("Something went wrong")).toBeVisible();
		expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
		expect(
			screen.queryByText("Run a flow to get started"),
		).not.toBeInTheDocument();
		expect(screen.getByPlaceholderText("Flow names")).toBeVisible();
	});
});
