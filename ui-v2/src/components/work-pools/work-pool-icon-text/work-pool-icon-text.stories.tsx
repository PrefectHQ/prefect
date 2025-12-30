import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { WorkPoolIconText } from "./work-pool-icon-text";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const createTestRouter = (workPoolName: string) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolIconText workPoolName={workPoolName} />,
	});

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient },
	});
};

const meta: Meta<typeof WorkPoolIconText> = {
	title: "Components/WorkPools/WorkPoolIconText",
	component: WorkPoolIconText,
	decorators: [
		(_Story, context) => {
			const router = createTestRouter(
				context.args.workPoolName ?? "my-work-pool",
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
					"A link component that displays a work pool name with a Cpu icon, linking to the work pool detail page.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolIconText>;

export const Default: Story = {
	args: {
		workPoolName: "my-work-pool",
	},
};
