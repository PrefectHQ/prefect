import type { Meta, StoryObj } from "@storybook/react";
import {
	createFakeArtifact,
	createFakeFlowRun,
	createFakeTaskRun,
} from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { ArtifactSection } from "./artifact-section";
import { FlowRunSection } from "./flow-run-section";
import { MetadataSidebar } from "./index";
import { LinksSection } from "./links-section";
import { TaskRunSection } from "./task-run-section";

// Mock data for stories
const mockArtifact = createFakeArtifact({
	key: "my-artifact-key",
	type: "markdown",
	created: "2026-01-15T10:30:00Z",
});

const mockFlowRun = createFakeFlowRun({
	name: "happy-dolphin",
	start_time: "2026-01-15T10:30:00Z",
	estimated_run_time: 45.5,
	created: "2026-01-15T10:29:00Z",
	updated: "2026-01-15T10:31:00Z",
	tags: ["production", "daily-run"],
	state: {
		id: "state-id",
		type: "COMPLETED",
		name: "Completed",
		timestamp: "2026-01-15T10:31:00Z",
		message: "Flow run completed successfully",
	},
});

const mockFlowRunNoTags = createFakeFlowRun({
	name: "quiet-penguin",
	start_time: "2026-01-15T10:30:00Z",
	estimated_run_time: 12.3,
	created: "2026-01-15T10:29:00Z",
	updated: "2026-01-15T10:31:00Z",
	tags: [],
	state: {
		id: "state-id",
		type: "RUNNING",
		name: "Running",
		timestamp: "2026-01-15T10:30:00Z",
		message: null,
	},
});

const mockTaskRun = createFakeTaskRun({
	name: "process-data-abc",
	created: "2026-01-15T10:30:15Z",
	updated: "2026-01-15T10:30:45Z",
	tags: ["etl", "transform"],
});

const mockTaskRunNoTags = createFakeTaskRun({
	name: "simple-task-xyz",
	created: "2026-01-15T10:30:15Z",
	updated: "2026-01-15T10:30:45Z",
	tags: [],
});

// ArtifactSection Stories
export const ArtifactSectionStory: StoryObj = {
	name: "ArtifactSection",
	render: () => <ArtifactSection artifact={mockArtifact} />,
};

// FlowRunSection Stories
export const FlowRunSectionWithTags: StoryObj = {
	name: "FlowRunSection - With Tags",
	render: () => <FlowRunSection flowRun={mockFlowRun} />,
};

export const FlowRunSectionNoTags: StoryObj = {
	name: "FlowRunSection - No Tags",
	render: () => <FlowRunSection flowRun={mockFlowRunNoTags} />,
};

// TaskRunSection Stories
export const TaskRunSectionWithTags: StoryObj = {
	name: "TaskRunSection - With Tags",
	render: () => <TaskRunSection taskRun={mockTaskRun} />,
};

export const TaskRunSectionNoTags: StoryObj = {
	name: "TaskRunSection - No Tags",
	render: () => <TaskRunSection taskRun={mockTaskRunNoTags} />,
};

// LinksSection Stories
export const LinksSectionAllLinks: StoryObj = {
	name: "LinksSection - All Links",
	decorators: [routerDecorator],
	render: () => (
		<LinksSection
			artifact={{
				...mockArtifact,
				flow_run: mockFlowRun,
				task_run: mockTaskRun,
			}}
		/>
	),
};

export const LinksSectionArtifactOnly: StoryObj = {
	name: "LinksSection - Artifact Only",
	decorators: [routerDecorator],
	render: () => (
		<LinksSection
			artifact={{
				...mockArtifact,
				flow_run: undefined,
				task_run: undefined,
			}}
		/>
	),
};

// MetadataSidebar Stories
export const MetadataSidebarComplete: StoryObj = {
	name: "MetadataSidebar - Complete",
	decorators: [routerDecorator],
	render: () => (
		<MetadataSidebar
			artifact={{
				...mockArtifact,
				flow_run: mockFlowRun,
				task_run: mockTaskRun,
			}}
		/>
	),
};

export const MetadataSidebarFlowRunOnly: StoryObj = {
	name: "MetadataSidebar - Flow Run Only",
	decorators: [routerDecorator],
	render: () => (
		<MetadataSidebar
			artifact={{
				...mockArtifact,
				flow_run: mockFlowRun,
				task_run: undefined,
			}}
		/>
	),
};

export const MetadataSidebarTaskRunOnly: StoryObj = {
	name: "MetadataSidebar - Task Run Only",
	decorators: [routerDecorator],
	render: () => (
		<MetadataSidebar
			artifact={{
				...mockArtifact,
				flow_run: undefined,
				task_run: mockTaskRun,
			}}
		/>
	),
};

export const MetadataSidebarArtifactOnly: StoryObj = {
	name: "MetadataSidebar - Artifact Only",
	decorators: [routerDecorator],
	render: () => (
		<MetadataSidebar
			artifact={{
				...mockArtifact,
				flow_run: undefined,
				task_run: undefined,
			}}
		/>
	),
};

export default {
	title: "Artifacts/MetadataSidebar",
	component: MetadataSidebar,
} satisfies Meta<typeof MetadataSidebar>;
