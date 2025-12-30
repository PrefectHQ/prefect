import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { Suspense } from "react";
import { WorkQueueIconText } from "./work-queue-icon-text";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const createTestRouter = (workPoolName: string, workQueueName: string) => {
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

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient },
	});
};

const meta: Meta<typeof WorkQueueIconText> = {
	title: "Components/WorkPools/WorkQueueIconText",
	component: WorkQueueIconText,
	decorators: [
		(_Story, context) => {
			const router = createTestRouter(
				context.args.workPoolName ?? "my-work-pool",
				context.args.workQueueName ?? "default",
			);
			return (
				<QueryClientProvider client={queryClient}>
					<RouterProvider router={router} />
				</QueryClientProvider>
			);
		},
	],
	parameters: {
		docs: {
			description: {
				component:
					"A link component that fetches and displays a work queue name with a ListOrdered icon, linking to the work queue detail page.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkQueueIconText>;

export const Default: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "default",
	},
};
