import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolMultiSelect } from "./work-pool-multi-select";

export default {
	title: "Components/WorkPools/WorkPoolMultiSelect",
	component: WorkPoolMultiSelect,
	decorators: [reactQueryDecorator, routerDecorator],
	render: function Render(args: ComponentProps<typeof WorkPoolMultiSelect>) {
		const [selectedWorkPoolIds, setSelectedWorkPoolIds] = useState<string[]>(
			args.selectedWorkPoolIds,
		);

		const handleToggleWorkPool = (workPoolId: string) => {
			setSelectedWorkPoolIds((prev) =>
				prev.includes(workPoolId)
					? prev.filter((id) => id !== workPoolId)
					: [...prev, workPoolId],
			);
		};

		return (
			<div className="w-80">
				<WorkPoolMultiSelect
					{...args}
					selectedWorkPoolIds={selectedWorkPoolIds}
					onToggleWorkPool={handleToggleWorkPool}
				/>
			</div>
		);
	},
} satisfies Meta<typeof WorkPoolMultiSelect>;

type Story = StoryObj<typeof WorkPoolMultiSelect>;

export const Default: Story = {
	args: {
		selectedWorkPoolIds: [],
		emptyMessage: "All work pools",
	},
};

export const WithEmptyMessage: Story = {
	args: {
		selectedWorkPoolIds: [],
		emptyMessage: "Select work pools",
	},
};
