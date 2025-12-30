import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { Suspense } from "react";
import { FlowIconText } from "./flow-icon-text";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const createTestRouter = (flowId: string) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<FlowIconText flowId={flowId} />
			</Suspense>
		),
	});

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient },
	});
};

const meta: Meta<typeof FlowIconText> = {
	title: "Components/Flows/FlowIconText",
	component: FlowIconText,
	decorators: [
		(_Story, context) => {
			const router = createTestRouter(context.args.flowId ?? "flow-123");
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
					"A link component that fetches and displays a flow name with a Workflow icon, linking to the flow detail page.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof FlowIconText>;

export const Default: Story = {
	args: {
		flowId: "flow-123",
	},
};
