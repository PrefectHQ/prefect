import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import { ResourceCombobox } from "./resource-combobox";

export default {
	title: "Components/Automations/Wizard/ResourceCombobox",
	component: ResourceCombobox,
	args: {
		selectedResources: [],
		onResourcesChange: fn(),
		emptyMessage: "All resources",
	},
	render: function Render(args: ComponentProps<typeof ResourceCombobox>) {
		const [selectedResources, setSelectedResources] = useState<string[]>(
			args.selectedResources,
		);

		return (
			<div className="w-96">
				<ResourceCombobox
					{...args}
					selectedResources={selectedResources}
					onResourcesChange={(resources) => {
						setSelectedResources(resources);
						args.onResourcesChange(resources);
					}}
				/>
				<p className="mt-4 text-sm text-muted-foreground">
					Selected:{" "}
					{selectedResources.length === 0
						? "None"
						: selectedResources.join(", ")}
				</p>
			</div>
		);
	},
} satisfies Meta<typeof ResourceCombobox>;

type Story = StoryObj<typeof ResourceCombobox>;

export const Default: Story = {};

export const WithSelectedResources: Story = {
	args: {
		selectedResources: ["prefect.flow.123", "prefect.deployment.456"],
	},
};

export const WithManySelectedResources: Story = {
	args: {
		selectedResources: [
			"prefect.flow.1",
			"prefect.flow.2",
			"prefect.deployment.3",
			"prefect.work-pool.4",
		],
	},
};

export const WithCustomResource: Story = {
	args: {
		selectedResources: ["prefect.custom.resource-id"],
	},
};

export const CustomEmptyMessage: Story = {
	args: {
		emptyMessage: "Select resources to filter...",
	},
};
