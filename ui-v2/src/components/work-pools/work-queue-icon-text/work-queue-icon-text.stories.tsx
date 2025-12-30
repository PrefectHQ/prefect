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

type StoryArgs = {
	workPoolName: string;
	workQueueName: string;
	showLabel?: boolean;
	showStatus?: boolean;
	className?: string;
	iconSize?: number;
};

const createTestRouter = (args: StoryArgs) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<WorkQueueIconText
					workPoolName={args.workPoolName}
					workQueueName={args.workQueueName}
					showLabel={args.showLabel}
					showStatus={args.showStatus}
					className={args.className}
					iconSize={args.iconSize}
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
			const router = createTestRouter({
				workPoolName: context.args.workPoolName ?? "my-work-pool",
				workQueueName: context.args.workQueueName ?? "default",
				showLabel: context.args.showLabel,
				showStatus: context.args.showStatus,
				className: context.args.className,
				iconSize: context.args.iconSize,
			});
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
					"A link component that fetches and displays a work queue name with a ListOrdered icon, linking to the work queue detail page. Supports optional label prefix and status badge.",
			},
		},
	},
	argTypes: {
		showLabel: {
			control: "boolean",
			description: 'When true, shows "Work Queue" text prefix before the link',
		},
		showStatus: {
			control: "boolean",
			description: "When true, shows the StatusIcon badge after the link",
		},
		className: {
			control: "text",
			description: "Custom CSS class for the link element",
		},
		iconSize: {
			control: "number",
			description: "Custom icon size in pixels",
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

export const WithLabel: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "default",
		showLabel: true,
	},
};

export const WithStatus: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "default",
		showStatus: true,
	},
};

export const WithLabelAndStatus: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "default",
		showLabel: true,
		showStatus: true,
	},
};

export const CustomIconSize: Story = {
	args: {
		workPoolName: "my-work-pool",
		workQueueName: "default",
		iconSize: 20,
	},
};
