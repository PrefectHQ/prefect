import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { reactQueryDecorator } from "@/storybook/utils";
import { WorkPoolFilter } from "./work-pool-filter";

const meta: Meta<typeof WorkPoolFilter> = {
	title: "Components/FlowRuns/WorkPoolFilter",
	component: WorkPoolFilter,
	decorators: [
		reactQueryDecorator,
		(Story) => (
			<div className="w-64">
				<Story />
			</div>
		),
	],
	parameters: {
		docs: {
			description: {
				component:
					"A combobox filter for selecting work pools to filter flow runs by.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolFilter>;

const WorkPoolFilterWithState = ({
	initialSelectedWorkPools = new Set<string>(),
}: {
	initialSelectedWorkPools?: Set<string>;
}) => {
	const [selectedWorkPools, setSelectedWorkPools] = useState<Set<string>>(
		initialSelectedWorkPools,
	);
	return (
		<WorkPoolFilter
			selectedWorkPools={selectedWorkPools}
			onSelectWorkPools={setSelectedWorkPools}
		/>
	);
};

const mockWorkPools = [
	createFakeWorkPool({ name: "default-agent-pool" }),
	createFakeWorkPool({ name: "kubernetes-pool" }),
	createFakeWorkPool({ name: "docker-pool" }),
	createFakeWorkPool({ name: "process-pool" }),
];

export const Default: Story = {
	render: () => <WorkPoolFilterWithState />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(mockWorkPools);
				}),
			],
		},
	},
};

export const WithSelectedWorkPools: Story = {
	render: () => (
		<WorkPoolFilterWithState
			initialSelectedWorkPools={
				new Set(["default-agent-pool", "kubernetes-pool"])
			}
		/>
	),
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(mockWorkPools);
				}),
			],
		},
	},
};

export const EmptyState: Story = {
	render: () => <WorkPoolFilterWithState />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const ErrorState: Story = {
	render: () => <WorkPoolFilterWithState />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.error();
				}),
			],
		},
	},
};
