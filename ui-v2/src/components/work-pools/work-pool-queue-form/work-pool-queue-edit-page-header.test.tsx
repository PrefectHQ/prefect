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
import { WorkPoolQueueEditPageHeader } from "./work-pool-queue-edit-page-header";

const HeaderRouter = (props: {
	workPoolName: string;
	workQueueName: string;
}) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolQueueEditPageHeader {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return <RouterProvider router={router} />;
};

describe("WorkPoolQueueEditPageHeader", () => {
	it("renders breadcrumbs correctly", async () => {
		await waitFor(() =>
			render(
				<HeaderRouter workPoolName="test-pool" workQueueName="test-queue" />,
				{ wrapper: createWrapper() },
			),
		);

		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toBeInTheDocument();
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText("test-pool")).toBeInTheDocument();
		expect(screen.getByText("test-queue")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
	});

	it("renders correct link destinations", async () => {
		await waitFor(() =>
			render(<HeaderRouter workPoolName="my-pool" workQueueName="my-queue" />, {
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

		const queueLink = screen.getByRole("link", { name: "my-queue" });
		expect(queueLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool/queue/my-queue",
		);
	});

	it("renders Edit as current page (not a link)", async () => {
		await waitFor(() =>
			render(
				<HeaderRouter workPoolName="test-pool" workQueueName="test-queue" />,
				{ wrapper: createWrapper() },
			),
		);

		const editText = screen.getByText("Edit");
		expect(editText).toBeInTheDocument();
		expect(editText.closest("a")).toBeNull();
		expect(editText).toHaveAttribute("aria-current", "page");
	});

	it("wraps content in a header element", async () => {
		const { container } = await waitFor(() =>
			render(
				<HeaderRouter workPoolName="test-pool" workQueueName="test-queue" />,
				{ wrapper: createWrapper() },
			),
		);

		const header = container.querySelector("header");
		expect(header).toBeInTheDocument();
	});
});
