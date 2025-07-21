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
import {
	ArtifactDetailHeader,
	type ArtifactDetailHeaderProps,
} from "./artifact-detail-header";

// Wraps component in test with a Tanstack router provider
const ArtifactDetailHeaderRouter = (props: ArtifactDetailHeaderProps) => {
	const rootRoute = createRootRoute({
		component: () => <ArtifactDetailHeader {...props} />,
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

describe("ArtifactDetailHeader", () => {
	it("renders artifact detail header with key", async () => {
		const artifact = createFakeArtifact({
			key: "test-key",
			id: "test-id",
		});

		const { getByText } = await waitFor(() =>
			render(<ArtifactDetailHeaderRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("test-key")).toBeTruthy();
		expect(getByText("test-key")).toHaveAttribute(
			"href",
			"/artifacts/key/test-key",
		);
		expect(getByText("test-id")).toBeTruthy();
	});

	it("renders artifact detail header with flow run and task run", async () => {
		const artifact = createFakeArtifact({
			id: "test-id",
			key: "",
			flow_run_id: "flow-run-id",
			task_run_id: "task-run-id",
		}) as ArtifactWithFlowRunAndTaskRun;

		const flowRun = createFakeFlowRun({
			id: "flow-run-id",
			name: "flow-run-name",
		});

		const taskRun = createFakeTaskRun({
			id: "task-run-id",
			name: "task-run-name",
		});

		artifact.flow_run = flowRun;
		artifact.task_run = taskRun;

		const { getByText } = await waitFor(() =>
			render(<ArtifactDetailHeaderRouter artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(getByText("flow-run-name")).toBeTruthy();
		expect(getByText("flow-run-name")).toHaveAttribute(
			"href",
			"/runs/flow-run/flow-run-id",
		);
		expect(getByText("task-run-name")).toBeTruthy();
		expect(getByText("task-run-name")).toHaveAttribute(
			"href",
			"/runs/task-run/task-run-id",
		);
		expect(getByText("test-id")).toBeTruthy();
	});
});
