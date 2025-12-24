import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeArtifact, createFakeFlowRun } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunArtifacts } from "./flow-run-artifacts";

const mockFlowRun = createFakeFlowRun({ id: "flow-run-1" });

const mockArtifacts = [
	createFakeArtifact({
		id: "artifact-1",
		key: "flow-table",
		type: "table",
		description:
			"Flow execution dataset with 1,234 rows and 5 columns: id, name, status, created_at, updated_at",
		flow_run_id: mockFlowRun.id,
	}),
	createFakeArtifact({
		id: "artifact-2",
		key: "flow-markdown",
		type: "markdown",
		description:
			"# Flow Summary\n\nExecution completed successfully with **99.1%** success rate.",
		flow_run_id: mockFlowRun.id,
	}),
	createFakeArtifact({
		id: "artifact-3",
		key: "flow-progress",
		type: "progress",
		description: "Flow completion: 95/100 tasks processed (95%)",
		flow_run_id: mockFlowRun.id,
	}),
];

const meta = {
	title: "Components/FlowRuns/FlowRunArtifacts",
	component: FlowRunArtifacts,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json(mockArtifacts);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunArtifacts>;

export default meta;
type Story = StoryObj<typeof FlowRunArtifacts>;

export const Default: Story = {
	args: {
		flowRun: mockFlowRun,
	},
};

export const Empty: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
	args: {
		flowRun: createFakeFlowRun({ id: "flow-run-empty" }),
	},
};

export const SingleArtifact: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					return HttpResponse.json([
						createFakeArtifact({
							id: "single-artifact",
							key: "single-table",
							type: "table",
							description: "Flow activity log with 500 entries",
							flow_run_id: "flow-run-single",
						}),
					]);
				}),
			],
		},
	},
	args: {
		flowRun: createFakeFlowRun({ id: "flow-run-single" }),
	},
};

export const ManyArtifacts: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					const manyFlowRun = createFakeFlowRun({ id: "flow-run-many" });
					return HttpResponse.json([
						createFakeArtifact({
							id: "many-artifact-1",
							key: "sales-data",
							type: "table",
							description:
								"Q4 sales data: 10,000 transactions across 5 regions",
							flow_run_id: manyFlowRun.id,
						}),
						createFakeArtifact({
							id: "many-artifact-2",
							key: "analysis-report",
							type: "markdown",
							description:
								"## Analysis Complete\n\nFound **3 anomalies** in the dataset.",
							flow_run_id: manyFlowRun.id,
						}),
						createFakeArtifact({
							id: "many-artifact-3",
							key: "etl-progress",
							type: "progress",
							description: "ETL pipeline: 450/500 records transformed (90%)",
							flow_run_id: manyFlowRun.id,
						}),
						createFakeArtifact({
							id: "many-artifact-4",
							key: "user-metrics",
							type: "table",
							description:
								"Daily active users: 2,500 rows with engagement scores",
							flow_run_id: manyFlowRun.id,
						}),
						createFakeArtifact({
							id: "many-artifact-5",
							key: "summary-notes",
							type: "markdown",
							description:
								"### Key Findings\n\n- Revenue up *12%*\n- Churn down *5%*",
							flow_run_id: manyFlowRun.id,
						}),
						createFakeArtifact({
							id: "many-artifact-6",
							key: "batch-progress",
							type: "progress",
							description:
								"Batch processing: 1,000/1,000 items complete (100%)",
							flow_run_id: manyFlowRun.id,
						}),
					]);
				}),
			],
		},
	},
	args: {
		flowRun: createFakeFlowRun({ id: "flow-run-many" }),
	},
};
