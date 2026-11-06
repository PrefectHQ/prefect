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
import { beforeAll, expect, test, vi } from "vitest";
import { buildListAutomationsQuery } from "@/api/automations";
import { createFakeAutomation } from "@/mocks";
import { AutomationsPage } from "./automations-page";

vi.mock("./automation-details", () => ({
	AutomationActions: () => null,
	AutomationDescription: () => null,
	AutomationTrigger: () => null,
}));
vi.mock("./automation-enable-toggle", () => ({
	AutomationEnableToggle: () => null,
}));
vi.mock("./automations-actions-menu", () => ({
	AutomationsActionsMenu: () => null,
}));
vi.mock("./automations-header", () => ({ AutomationsHeader: () => null }));

beforeAll(mockPointerEvents);

test.each([1, 2, 3])(
	"searches and sorts across pages of %i automations",
	async (pageSize) => {
		const automations = [
			createFakeAutomation({ id: "1", name: "Alpha", enabled: false }),
			createFakeAutomation({ id: "2", name: "Zulu", enabled: true }),
			createFakeAutomation({ id: "3", name: "Beta", enabled: true }),
		];
		const sorts: Array<string> = [];
		server.use(
			http.post(buildApiUrl("/automations/filter"), async ({ request }) => {
				const { sort, offset = 0 } = (await request.json()) as {
					sort: string;
					offset?: number;
				};
				if (offset === 0) sorts.push(sort);
				return HttpResponse.json(
					sort === "NAME_ASC"
						? [...automations]
								.sort((a, b) => a.name.localeCompare(b.name))
								.slice(offset, offset + pageSize)
						: automations.slice(offset, offset + pageSize),
				);
			}),
		);

		const queryClient = new QueryClient();
		queryClient.setQueryData(buildListAutomationsQuery().queryKey, [
			automations[0],
		]);
		const rootRoute = createRootRoute({ component: AutomationsPage });
		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient },
		});
		const user = userEvent.setup();
		render(<RouterProvider router={router} />, {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() =>
			expect(
				screen.getAllByRole("link").map((link) => link.textContent),
			).toEqual(["Zulu", "Beta", "Alpha"]),
		);

		await user.type(screen.getByRole("searchbox"), " beta ");
		await waitFor(() =>
			expect(
				screen.getAllByRole("link").map((link) => link.textContent),
			).toEqual(["Beta"]),
		);

		await user.clear(screen.getByRole("searchbox"));
		await user.click(
			screen.getByRole("combobox", { name: "Automation sort order" }),
		);
		await user.click(screen.getByRole("option", { name: "Name: A to Z" }));

		await waitFor(() => {
			expect(sorts).toEqual(["CREATED_DESC", "NAME_ASC"]);
			expect(
				screen.getAllByRole("link").map((link) => link.textContent),
			).toEqual(["Alpha", "Beta", "Zulu"]);
		});
	},
);
