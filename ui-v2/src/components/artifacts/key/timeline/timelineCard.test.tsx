import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import type { Artifact, ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	createFakeArtifact,
	createFakeFlowRun,
	createFakeTaskRun,
} from "@/mocks";
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
	it("renders timeline card with link", async () => {
		const artifact: Artifact = createFakeArtifact({
			id: "test-id",
		});

		const { getByText } = await waitFor(() =>
			render(<TimelineCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("test")).toBeTruthy();
	});

	it("renders timeline card with link to flow run", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = createFakeArtifact({
			id: "test-id",
		});

		const flowRun = createFakeFlowRun({
			id: "test-flow-run",
			name: "Test Flow Run",
		});

		artifact.flow_run = flowRun;

		const { getByText } = await waitFor(() =>
			render(<TimelineCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("Test Flow Run")).toBeTruthy();
	});

	it("renders timeline card with link to task run", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = createFakeArtifact({
			id: "test-id",
		});

		const taskRun = createFakeTaskRun({
			id: "test-task-run",
			name: "Test Task Run",
		});

		artifact.task_run = taskRun;

		const { getByText } = await waitFor(() =>
			render(<TimelineCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("Test Task Run")).toBeTruthy();
	});
});
