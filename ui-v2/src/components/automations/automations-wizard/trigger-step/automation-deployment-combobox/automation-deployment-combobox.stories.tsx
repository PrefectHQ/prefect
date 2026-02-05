import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import { AutomationDeploymentCombobox } from "./index";

export default {
	title: "Components/Automations/AutomationDeploymentCombobox",
	component: AutomationDeploymentCombobox,
	args: {
		selectedDeploymentIds: [],
		onSelectDeploymentIds: fn(),
	},
	render: function Render(
		args: ComponentProps<typeof AutomationDeploymentCombobox>,
	) {
		const [selectedDeploymentIds, setSelectedDeploymentIds] = useState(
			args.selectedDeploymentIds,
		);

		return (
			<div className="w-80">
				<AutomationDeploymentCombobox
					{...args}
					selectedDeploymentIds={selectedDeploymentIds}
					onSelectDeploymentIds={(ids) => {
						setSelectedDeploymentIds(ids);
						args.onSelectDeploymentIds(ids);
					}}
				/>
			</div>
		);
	},
} satisfies Meta<typeof AutomationDeploymentCombobox>;

type Story = StoryObj<typeof AutomationDeploymentCombobox>;

export const Default: Story = {};

export const WithSelectedDeployments: Story = {
	args: {
		selectedDeploymentIds: ["deployment-1", "deployment-2"],
	},
};
