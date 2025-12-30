import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import { createFakeWorkQueue } from "@/mocks";
import { WorkQueueIconText } from "./work-queue-icon-text";

const mockWorkQueue = createFakeWorkQueue({
	id: "work-queue-123",
	name: "my-work-queue",
	work_pool_name: "my-work-pool",
});

type WorkQueueIconTextRouterProps = {
	workPoolName: string;
	workQueueName: string;
};

const WorkQueueIconTextRouter = ({
	workPoolName,
	workQueueName,
}: WorkQueueIconTextRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<WorkQueueIconText
					workPoolName={workPoolName}
					workQueueName={workQueueName}
				/>
			</Suspense>
		),
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

describe("WorkQueueIconText", () => {
	it("fetches and displays work queue name", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("my-work-queue")).toBeInTheDocument();
		});
	});

	it("renders a link to the work queue detail page", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute(
				"href",
				"/work-pools/work-pool/my-work-pool/queue/my-work-queue",
			);
		});
	});
});
