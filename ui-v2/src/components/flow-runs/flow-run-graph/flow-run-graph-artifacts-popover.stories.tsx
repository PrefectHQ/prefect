import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphArtifactsPopover } from "./flow-run-graph-artifacts-popover";

const meta = {
	component: FlowRunGraphArtifactsPopover,
	title: "Components/FlowRuns/FlowRunGraphArtifactsPopover",
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof FlowRunGraphArtifactsPopover>;

export default meta;

type Story = StoryObj<typeof meta>;

const defaultPosition = { x: 200, y: 100, width: 20, height: 20 };

export const Default: Story = {
	args: {
		artifacts: [
			{ id: "artifact-1", key: "processed-data", type: "result" },
			{ id: "artifact-2", key: "summary-report", type: "markdown" },
			{ id: "artifact-3", key: "metrics-table", type: "table" },
		],
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};

export const SingleArtifact: Story = {
	args: {
		artifacts: [{ id: "artifact-1", key: "my-artifact", type: "result" }],
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};

export const VariousTypes: Story = {
	args: {
		artifacts: [
			{ id: "artifact-1", key: "computation-result", type: "result" },
			{ id: "artifact-2", key: "readme", type: "markdown" },
			{ id: "artifact-3", key: "data-summary", type: "table" },
			{ id: "artifact-4", key: "progress-info", type: "progress" },
			{ id: "artifact-5", key: "external-link", type: "link" },
			{ id: "artifact-6", key: "visualization", type: "image" },
		],
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};

export const UnnamedArtifact: Story = {
	args: {
		artifacts: [
			{ id: "artifact-1", key: null, type: "result" },
			{ id: "artifact-2", key: "named-artifact", type: "markdown" },
		],
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};

export const NoType: Story = {
	args: {
		artifacts: [{ id: "artifact-1", key: "artifact-without-type", type: null }],
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};

export const ManyArtifacts: Story = {
	args: {
		artifacts: Array.from({ length: 10 }, (_, i) => ({
			id: `artifact-${i + 1}`,
			key: `artifact-key-${i + 1}`,
			type: ["result", "markdown", "table", "progress", "link"][i % 5],
		})),
		position: defaultPosition,
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
};
