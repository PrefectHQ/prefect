import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FlowIconText } from "./flow-icon-text";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const meta: Meta<typeof FlowIconText> = {
	title: "Components/Flows/FlowIconText",
	component: FlowIconText,
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<Story />
			</QueryClientProvider>
		),
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
