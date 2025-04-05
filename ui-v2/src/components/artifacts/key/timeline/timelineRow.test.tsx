import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
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
	it("renders timeline rows", () => {
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

		const { getByTestId } = render(<TimelineCardRouter artifact={artifact} />, {
			wrapper: createWrapper(),
		});

		expect(getByTestId("timeline-row-test-id")).toBeTruthy();
	});
});
