import type { Artifact, ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	createFakeArtifact,
	createFakeFlowRun,
	createFakeTaskRun,
} from "@/mocks";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import {
	ArtifactTimelineCard,
	type ArtifactTimelineCardProps,
} from "./timelineCard";

// Wraps component in test with a Tanstack router provider
const TimelineCardRouter = (props: ArtifactTimelineCardProps) => {
	const rootRoute = createRootRoute({
		component: () => <ArtifactTimelineCard {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("Artifacts Card", () => {
	it("renders timeline card with link", () => {
		const artifact: Artifact = createFakeArtifact({
			id: "test-id",
		});

		const { getByText } = render(<TimelineCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("test")).toBeTruthy();
	});

	it("renders timeline card with link to flow run", () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = createFakeArtifact({
			id: "test-id",
		});

		const flowRun = createFakeFlowRun({
			id: "test-flow-run",
			name: "Test Flow Run",
		});

		artifact.flow_run = flowRun;

		const { getByText } = render(<TimelineCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("Test Flow Run")).toBeTruthy();
	});

	it("renders timeline card with link to task run", () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = createFakeArtifact({
			id: "test-id",
		});

		const taskRun = createFakeTaskRun({
			id: "test-task-run",
			name: "Test Task Run",
		});

		artifact.task_run = taskRun;

		const { getByText } = render(<TimelineCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByText("Test Task Run")).toBeTruthy();
	});
});
