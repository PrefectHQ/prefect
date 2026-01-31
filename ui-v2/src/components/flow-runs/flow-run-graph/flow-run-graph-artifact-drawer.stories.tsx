import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunGraphArtifactDrawer } from "./flow-run-graph-artifact-drawer";

const meta = {
	component: FlowRunGraphArtifactDrawer,
	title: "Components/FlowRuns/FlowRunGraphArtifactDrawer",
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof FlowRunGraphArtifactDrawer>;

export default meta;

type Story = StoryObj<typeof meta>;

const createMockArtifact = (overrides = {}) => ({
	id: "artifact-123",
	key: "my-artifact",
	type: "result",
	description: "A test artifact description",
	created: "2024-01-15T10:30:00Z",
	data: { value: 42, status: "success" },
	flow_run_id: "flow-run-123",
	task_run_id: null,
	updated: "2024-01-15T10:30:00Z",
	...overrides,
});

export const Default: Story = {
	args: {
		artifactId: "artifact-123",
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json(createMockArtifact());
				}),
			],
		},
	},
};

export const MarkdownArtifact: Story = {
	args: {
		artifactId: "artifact-markdown",
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json(
						createMockArtifact({
							id: "artifact-markdown",
							key: "readme-content",
							type: "markdown",
							description: "Documentation for the pipeline",
							data: "# Pipeline Results\n\n## Summary\n\nThe pipeline completed successfully.\n\n- Processed 1000 records\n- Duration: 45 seconds\n- Status: Success",
						}),
					);
				}),
			],
		},
	},
};

export const TableArtifact: Story = {
	args: {
		artifactId: "artifact-table",
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json(
						createMockArtifact({
							id: "artifact-table",
							key: "metrics-summary",
							type: "table",
							description: "Performance metrics for the run",
							data: [
								{ metric: "latency", value: 120, unit: "ms" },
								{ metric: "throughput", value: 1500, unit: "req/s" },
								{ metric: "error_rate", value: 0.02, unit: "%" },
							],
						}),
					);
				}),
			],
		},
	},
};

export const UnnamedArtifact: Story = {
	args: {
		artifactId: "artifact-unnamed",
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json(
						createMockArtifact({
							id: "artifact-unnamed",
							key: null,
							type: "result",
							description: null,
							data: { computed: true, result: 123 },
						}),
					);
				}),
			],
		},
	},
};

export const StringDataArtifact: Story = {
	args: {
		artifactId: "artifact-string",
		onClose: () => console.log("Close clicked"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json(
						createMockArtifact({
							id: "artifact-string",
							key: "log-output",
							type: "result",
							description: "Raw log output from the process",
							data: "Process started at 10:30:00\nLoading data...\nProcessing 1000 records...\nCompleted successfully at 10:30:45",
						}),
					);
				}),
			],
		},
	},
};

export const Closed: Story = {
	args: {
		artifactId: null,
		onClose: () => console.log("Close clicked"),
	},
};
