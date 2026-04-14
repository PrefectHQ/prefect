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
import { WorkPoolQueueCreatePageHeader } from "./work-pool-queue-create-page-header";

const HeaderRouter = (props: { workPoolName: string }) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolQueueCreatePageHeader {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return <RouterProvider router={router} />;
};

describe("WorkPoolQueueCreatePageHeader", () => {
	it("renders breadcrumbs correctly", async () => {
		await waitFor(() =>
			render(<HeaderRouter workPoolName="test-pool" />, {
				wrapper: createWrapper(),
			}),
		);

		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toBeInTheDocument();
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText("test-pool")).toBeInTheDocument();
		expect(screen.getByText("Create Work Queue")).toBeInTheDocument();
	});

	it("renders correct link destinations", async () => {
		await waitFor(() =>
			render(<HeaderRouter workPoolName="my-pool" />, {
				wrapper: createWrapper(),
			}),
		);

		const workPoolsLink = screen.getByRole("link", { name: "Work Pools" });
		expect(workPoolsLink).toHaveAttribute("href", "/work-pools");

		const workPoolLink = screen.getByRole("link", { name: "my-pool" });
		expect(workPoolLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool",
		);
	});

	it("renders Create Work Queue as current page (not a link)", async () => {
		await waitFor(() =>
			render(<HeaderRouter workPoolName="test-pool" />, {
				wrapper: createWrapper(),
			}),
		);

		const createText = screen.getByText("Create Work Queue");
		expect(createText).toBeInTheDocument();
		expect(createText.closest("a")).toBeNull();
		expect(createText).toHaveAttribute("aria-current", "page");
	});

	it("wraps content in a header element", async () => {
		const { container } = await waitFor(() =>
			render(<HeaderRouter workPoolName="test-pool" />, {
				wrapper: createWrapper(),
			}),
		);

		const header = container.querySelector("header");
		expect(header).toBeInTheDocument();
	});
});
