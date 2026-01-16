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
	status: "READY",
});

type WorkQueueIconTextRouterProps = {
	workPoolName: string;
	workQueueName: string;
	showLabel?: boolean;
	showStatus?: boolean;
	className?: string;
	iconSize?: number;
};

const WorkQueueIconTextRouter = ({
	workPoolName,
	workQueueName,
	showLabel,
	showStatus,
	className,
	iconSize,
}: WorkQueueIconTextRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<WorkQueueIconText
					workPoolName={workPoolName}
					workQueueName={workQueueName}
					showLabel={showLabel}
					showStatus={showStatus}
					className={className}
					iconSize={iconSize}
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

	it("does not show label by default", async () => {
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

		expect(screen.queryByText("Work Queue")).not.toBeInTheDocument();
	});

	it("shows label when showLabel is true", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
				showLabel
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("Work Queue")).toBeInTheDocument();
		});
	});

	it("shows status icon when showStatus is true and work queue has status", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		const { container } = render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
				showStatus
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("my-work-queue")).toBeInTheDocument();
		});

		// StatusIcon renders a Circle SVG for READY status
		const statusIcon = container.querySelector("svg.lucide-circle");
		expect(statusIcon).toBeInTheDocument();
	});

	it("shows both label and status when both props are true", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		const { container } = render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
				showLabel
				showStatus
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("Work Queue")).toBeInTheDocument();
			expect(screen.getByText("my-work-queue")).toBeInTheDocument();
		});

		const statusIcon = container.querySelector("svg.lucide-circle");
		expect(statusIcon).toBeInTheDocument();
	});

	it("applies custom className to the link", async () => {
		server.use(
			http.get(buildApiUrl("/work_pools/:work_pool_name/queues/:name"), () => {
				return HttpResponse.json(mockWorkQueue);
			}),
		);

		render(
			<WorkQueueIconTextRouter
				workPoolName="my-work-pool"
				workQueueName="my-work-queue"
				className="custom-class"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveClass("custom-class");
		});
	});
});
