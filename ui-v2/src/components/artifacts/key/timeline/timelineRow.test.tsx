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
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	createFakeArtifact,
	createFakeFlowRun,
	createFakeTaskRun,
} from "@/mocks";
import { TimelineRow, type TimelineRowProps } from "./timelineRow";

// Wraps component in test with a Tanstack router provider
const TimelineCardRouter = (props: TimelineRowProps) => {
	const rootRoute = createRootRoute({
		component: () => <TimelineRow {...props} />,
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

describe("Timeline Container", () => {
	it("renders timeline rows", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = createFakeArtifact({
			id: "test-id",
		});

		const flowRun = createFakeFlowRun({
			id: "test-flow-run",
			name: "Test Flow Run",
		});

		const taskRun = createFakeTaskRun({
			id: "test-task-run",
			name: "Test Task Run",
		});

		artifact.flow_run = flowRun;
		artifact.task_run = taskRun;

		const { getByTestId } = await waitFor(() =>
			render(<TimelineCardRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByTestId("timeline-row-test-id")).toBeTruthy();
	});
});
