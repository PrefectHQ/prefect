import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

// Create a mock router for Storybook
const queryClient = new QueryClient({
	defaultOptions: {
		queries: { retry: false, staleTime: Number.POSITIVE_INFINITY },
		mutations: { retry: false },
	},
});

const meta = {
	title: "Components/WorkPools/WorkPoolCreateWizard",
	component: WorkPoolCreateWizard,
	parameters: {
		layout: "padded",
	},
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<div className="max-w-4xl mx-auto">
					<Story />
				</div>
			</QueryClientProvider>
		),
	],
} satisfies Meta<typeof WorkPoolCreateWizard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithMockData: Story = {
	...Default,
};
