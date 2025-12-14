import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { DeploymentFilter } from "./deployment-filter";

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

const meta: Meta<typeof DeploymentFilter> = {
	title: "Components/FlowRuns/DeploymentFilter",
	component: DeploymentFilter,
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
					"A combobox filter for selecting deployments to filter flow runs by.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof DeploymentFilter>;

const DeploymentFilterWithState = ({
	initialSelectedDeployments = new Set<string>(),
}: {
	initialSelectedDeployments?: Set<string>;
}) => {
	const [selectedDeployments, setSelectedDeployments] = useState<Set<string>>(
		initialSelectedDeployments,
	);
	return (
		<DeploymentFilter
			selectedDeployments={selectedDeployments}
			onSelectDeployments={setSelectedDeployments}
		/>
	);
};

export const Default: Story = {
	render: () => <DeploymentFilterWithState />,
};

export const WithSelectedDeployments: Story = {
	render: () => (
		<DeploymentFilterWithState
			initialSelectedDeployments={new Set(["deployment-1", "deployment-2"])}
		/>
	),
};
