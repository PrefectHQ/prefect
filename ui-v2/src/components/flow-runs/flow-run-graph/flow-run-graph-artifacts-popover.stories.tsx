import type { ArtifactsSelection } from "@prefecthq/graphs";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
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

const createSelection = (
	ids: string[],
	position = { x: 200, y: 100, width: 20, height: 20 },
): ArtifactsSelection => ({
	kind: "artifacts",
	ids,
	position,
});

const createArtifactResponse = (
	id: string,
	key: string | null,
	type: string | null,
) => ({
	id,
	key,
	type,
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
});

export const Default: Story = {
	args: {
		selection: createSelection(["artifact-1", "artifact-2", "artifact-3"]),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createArtifactResponse("artifact-1", "processed-data", "result"),
						createArtifactResponse("artifact-2", "summary-report", "markdown"),
						createArtifactResponse("artifact-3", "metrics-table", "table"),
					]);
				}),
			],
		},
	},
};

export const SingleArtifact: Story = {
	args: {
		selection: createSelection(["artifact-1"]),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createArtifactResponse("artifact-1", "my-artifact", "result"),
					]);
				}),
			],
		},
	},
};

export const VariousTypes: Story = {
	args: {
		selection: createSelection([
			"artifact-1",
			"artifact-2",
			"artifact-3",
			"artifact-4",
			"artifact-5",
			"artifact-6",
		]),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createArtifactResponse(
							"artifact-1",
							"computation-result",
							"result",
						),
						createArtifactResponse("artifact-2", "readme", "markdown"),
						createArtifactResponse("artifact-3", "data-summary", "table"),
						createArtifactResponse("artifact-4", "progress-info", "progress"),
						createArtifactResponse("artifact-5", "external-link", "link"),
						createArtifactResponse("artifact-6", "visualization", "image"),
					]);
				}),
			],
		},
	},
};

export const UnnamedArtifact: Story = {
	args: {
		selection: createSelection(["artifact-1", "artifact-2"]),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createArtifactResponse("artifact-1", null, "result"),
						createArtifactResponse("artifact-2", "named-artifact", "markdown"),
					]);
				}),
			],
		},
	},
};

export const NoType: Story = {
	args: {
		selection: createSelection(["artifact-1"]),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createArtifactResponse("artifact-1", "artifact-without-type", null),
					]);
				}),
			],
		},
	},
};

export const ManyArtifacts: Story = {
	args: {
		selection: createSelection(
			Array.from({ length: 10 }, (_, i) => `artifact-${i + 1}`),
		),
		onClose: () => console.log("Close clicked"),
		onViewArtifact: (id) => console.log("View artifact:", id),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json(
						Array.from({ length: 10 }, (_, i) =>
							createArtifactResponse(
								`artifact-${i + 1}`,
								`artifact-key-${i + 1}`,
								["result", "markdown", "table", "progress", "link"][i % 5],
							),
						),
					);
				}),
			],
		},
	},
};
