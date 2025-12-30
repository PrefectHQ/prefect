import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { FlowMultiSelect } from "./flow-multi-select";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const meta: Meta<typeof FlowMultiSelect> = {
	title: "Components/Flows/FlowMultiSelect",
	component: FlowMultiSelect,
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
					"A multi-select combobox for selecting multiple flows. Used in automation triggers to filter by specific flows.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof FlowMultiSelect>;

const FlowMultiSelectWithState = ({
	initialSelectedFlowIds = [],
	emptyMessage = "Any flow",
}: {
	initialSelectedFlowIds?: string[];
	emptyMessage?: string;
}) => {
	const [selectedFlowIds, setSelectedFlowIds] = useState<string[]>(
		initialSelectedFlowIds,
	);
	const handleToggleFlow = (flowId: string) => {
		setSelectedFlowIds((prev) =>
			prev.includes(flowId)
				? prev.filter((id) => id !== flowId)
				: [...prev, flowId],
		);
	};
	return (
		<FlowMultiSelect
			selectedFlowIds={selectedFlowIds}
			onToggleFlow={handleToggleFlow}
			emptyMessage={emptyMessage}
		/>
	);
};

export const Default: Story = {
	render: () => <FlowMultiSelectWithState />,
};

export const WithCustomEmptyMessage: Story = {
	render: () => <FlowMultiSelectWithState emptyMessage="Select flows..." />,
};

export const WithSelectedFlows: Story = {
	render: () => (
		<FlowMultiSelectWithState
			initialSelectedFlowIds={["flow-1", "flow-2", "flow-3"]}
		/>
	),
};
