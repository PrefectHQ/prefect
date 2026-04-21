import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import type { Automation } from "@/api/automations";
import { createFakeAutomation } from "@/mocks/create-fake-automation";
import { AutomationsEditHeader } from "./automations-edit-header";

const HeaderRouter = ({ automation }: { automation: Automation }) => {
	const rootRoute = createRootRoute({
		component: () => <AutomationsEditHeader automation={automation} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("AutomationsEditHeader", () => {
	it("renders breadcrumbs with the automation name and Edit segment", async () => {
		const automation = createFakeAutomation({ name: "my-automation" });
		await waitFor(() =>
			render(<HeaderRouter automation={automation} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(
			screen.getByRole("navigation", { name: /breadcrumb/i }),
		).toBeInTheDocument();
		expect(screen.getByText("Automations")).toBeInTheDocument();
		expect(screen.getByText("my-automation")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
	});

	it("links the automation name back to its details page", async () => {
		const automation = createFakeAutomation({
			id: "abc-123",
			name: "my-automation",
		});
		await waitFor(() =>
			render(<HeaderRouter automation={automation} />, {
				wrapper: createWrapper(),
			}),
		);

		const automationsLink = screen.getByRole("link", { name: "Automations" });
		expect(automationsLink).toHaveAttribute("href", "/automations");

		const automationLink = screen.getByRole("link", { name: "my-automation" });
		expect(automationLink).toHaveAttribute(
			"href",
			"/automations/automation/abc-123",
		);
	});

	it("renders Edit as the current page (not a link)", async () => {
		const automation = createFakeAutomation({ name: "my-automation" });
		await waitFor(() =>
			render(<HeaderRouter automation={automation} />, {
				wrapper: createWrapper(),
			}),
		);

		const editText = screen.getByText("Edit");
		expect(editText.closest("a")).toBeNull();
		expect(editText).toHaveAttribute("aria-current", "page");
	});
});
