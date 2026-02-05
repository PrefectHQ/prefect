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
import { WorkPoolIconText } from "./work-pool-icon-text";

type WorkPoolIconTextRouterProps = {
	workPoolName: string;
};

const WorkPoolIconTextRouter = ({
	workPoolName,
}: WorkPoolIconTextRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolIconText workPoolName={workPoolName} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("WorkPoolIconText", () => {
	it("displays work pool name", async () => {
		render(<WorkPoolIconTextRouter workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-work-pool")).toBeInTheDocument();
		});
	});

	it("renders a link to the work pool detail page", async () => {
		render(<WorkPoolIconTextRouter workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute(
				"href",
				"/work-pools/work-pool/my-work-pool",
			);
		});
	});

	it("displays the Cpu icon", async () => {
		render(<WorkPoolIconTextRouter workPoolName="my-work-pool" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const icon = document.querySelector("svg");
			expect(icon).toBeInTheDocument();
		});
	});
});
