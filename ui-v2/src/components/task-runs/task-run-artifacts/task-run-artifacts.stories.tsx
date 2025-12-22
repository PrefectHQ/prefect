import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeArtifact, createFakeTaskRun } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TaskRunArtifacts } from ".";

const mockTaskRun = createFakeTaskRun({ id: "task-run-1" });

const mockArtifacts = [
	createFakeArtifact({
		id: "artifact-1",
		key: "my-table",
		type: "table",
		description:
			"Dataset with 1,234 rows and 5 columns: id, name, status, created_at, updated_at",
		task_run_id: mockTaskRun.id,
		flow_run_id: mockTaskRun.flow_run_id,
	}),
	createFakeArtifact({
		id: "artifact-2",
		key: "my-markdown",
		type: "markdown",
		description:
			"# Summary Report\n\nProcessing completed successfully with **98.5%** accuracy.",
		task_run_id: mockTaskRun.id,
		flow_run_id: mockTaskRun.flow_run_id,
	}),
	createFakeArtifact({
		id: "artifact-3",
		key: "my-progress",
		type: "progress",
		description: "Task completion: 75/100 items processed (75%)",
		task_run_id: mockTaskRun.id,
		flow_run_id: mockTaskRun.flow_run_id,
	}),
];

const meta = {
	title: "Components/TaskRuns/TaskRunArtifacts",
	component: TaskRunArtifacts,
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
} satisfies Meta<typeof TaskRunArtifacts>;

export default meta;
type Story = StoryObj<typeof TaskRunArtifacts>;

export const Default: Story = {
	args: {
		taskRun: mockTaskRun,
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
		taskRun: createFakeTaskRun({ id: "task-run-empty" }),
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
							description: "User activity log with 500 entries",
							task_run_id: "task-run-single",
						}),
					]);
				}),
			],
		},
	},
	args: {
		taskRun: createFakeTaskRun({ id: "task-run-single" }),
	},
};

export const ManyArtifacts: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/artifacts/filter"), () => {
					const manyTaskRun = createFakeTaskRun({ id: "task-run-many" });
					return HttpResponse.json([
						createFakeArtifact({
							id: "many-artifact-1",
							key: "sales-data",
							type: "table",
							description:
								"Q4 sales data: 10,000 transactions across 5 regions",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-2",
							key: "analysis-report",
							type: "markdown",
							description:
								"## Analysis Complete\n\nFound **3 anomalies** in the dataset.",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-3",
							key: "etl-progress",
							type: "progress",
							description: "ETL pipeline: 450/500 records transformed (90%)",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-4",
							key: "user-metrics",
							type: "table",
							description:
								"Daily active users: 2,500 rows with engagement scores",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-5",
							key: "summary-notes",
							type: "markdown",
							description:
								"### Key Findings\n\n- Revenue up *12%*\n- Churn down *5%*",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-6",
							key: "batch-progress",
							type: "progress",
							description:
								"Batch processing: 1,000/1,000 items complete (100%)",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
					]);
				}),
			],
		},
	},
	args: {
		taskRun: createFakeTaskRun({ id: "task-run-many" }),
	},
};
