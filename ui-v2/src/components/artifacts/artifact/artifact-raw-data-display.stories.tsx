import type { Meta, StoryObj } from "@storybook/react";
import { ArtifactDataDisplay } from "./artifact-raw-data-display";

const meta: Meta<typeof ArtifactDataDisplay> = {
	title: "Components/Artifacts/ArtifactDataDisplay",
	component: ArtifactDataDisplay,
};

export default meta;
type Story = StoryObj<typeof ArtifactDataDisplay>;

const mockArtifact = {
	data: JSON.stringify(
		{
			sample: "data",
			nested: {
				value: 123,
				array: [1, 2, 3],
			},
		},
		null,
		2,
	),
	// Add other required properties from ArtifactWithFlowRunAndTaskRun
	id: "test-artifact-id",
	key: "test-artifact",
	type: "json",
	created: new Date().toISOString(),
	updated: new Date().toISOString(),
	flow_run_id: "test-flow-run-id",
	task_run_id: "test-task-run-id",
};

export const Default: Story = {
	args: {
		artifact: mockArtifact,
	},
};

export const LongData: Story = {
	args: {
		artifact: {
			...mockArtifact,
			data: JSON.stringify(
				{
					longArray: Array.from({ length: 100 }, (_, i) => ({
						id: i,
						value: `Item ${i}`,
						timestamp: new Date().toISOString(),
					})),
				},
				null,
				2,
			),
		},
	},
};
