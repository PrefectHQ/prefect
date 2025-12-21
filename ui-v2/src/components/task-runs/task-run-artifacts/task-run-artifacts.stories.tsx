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
		task_run_id: mockTaskRun.id,
		flow_run_id: mockTaskRun.flow_run_id,
	}),
	createFakeArtifact({
		id: "artifact-2",
		key: "my-markdown",
		type: "markdown",
		task_run_id: mockTaskRun.id,
		flow_run_id: mockTaskRun.flow_run_id,
	}),
	createFakeArtifact({
		id: "artifact-3",
		key: "my-progress",
		type: "progress",
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
							key: "table-1",
							type: "table",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-2",
							key: "markdown-1",
							type: "markdown",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-3",
							key: "progress-1",
							type: "progress",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-4",
							key: "table-2",
							type: "table",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-5",
							key: "markdown-2",
							type: "markdown",
							task_run_id: manyTaskRun.id,
							flow_run_id: manyTaskRun.flow_run_id,
						}),
						createFakeArtifact({
							id: "many-artifact-6",
							key: "progress-2",
							type: "progress",
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
