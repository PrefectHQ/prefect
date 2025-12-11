import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { FlowFilter } from "./flow-filter";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const meta: Meta<typeof FlowFilter> = {
	title: "Components/FlowRuns/FlowFilter",
	component: FlowFilter,
	decorators: [
		(Story) => (
			<QueryClientProvider client={queryClient}>
				<div className="w-64">
					<Story />
				</div>
			</QueryClientProvider>
		),
	],
	parameters: {
		docs: {
			description: {
				component:
					"A combobox filter for selecting flows to filter flow runs by.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof FlowFilter>;

const FlowFilterWithState = ({
	initialSelectedFlows = new Set<string>(),
}: {
	initialSelectedFlows?: Set<string>;
}) => {
	const [selectedFlows, setSelectedFlows] =
		useState<Set<string>>(initialSelectedFlows);
	return (
		<FlowFilter
			selectedFlows={selectedFlows}
			onSelectFlows={setSelectedFlows}
		/>
	);
};

export const Default: Story = {
	render: () => <FlowFilterWithState />,
};

export const WithSelectedFlows: Story = {
	render: () => (
		<FlowFilterWithState initialSelectedFlows={new Set(["flow-1", "flow-2"])} />
	),
};
