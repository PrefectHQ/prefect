import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import {
	createFakeArtifact,
	createFakeFlowRun,
	createFakeTaskRun,
} from "@/mocks";
import { MetadataSidebar, type MetadataSidebarProps } from "./index";

const MetadataSidebarWrapper = (props: MetadataSidebarProps) => {
	const rootRoute = createRootRoute({
		component: () => <MetadataSidebar {...props} />,
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

describe("MetadataSidebar", () => {
	it("renders artifact section", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact({ key: "test-key", type: "markdown" }),
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		// Check for the artifact section elements
		expect(screen.getByText("Key")).toBeTruthy();
		expect(screen.getAllByText("test-key").length).toBeGreaterThan(0);
		expect(screen.getByText("Type")).toBeTruthy();
		expect(screen.getByText("markdown")).toBeTruthy();
	});

	it("renders flow run section when flow_run exists", async () => {
		const flowRun = createFakeFlowRun({ name: "test-flow-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			flow_run: flowRun,
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Start time")).toBeTruthy();
		expect(screen.getByText("Duration")).toBeTruthy();
		expect(screen.getByText("test-flow-run")).toBeTruthy();
	});

	it("renders task run section when task_run exists", async () => {
		const taskRun = createFakeTaskRun({ name: "test-task-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			task_run: taskRun,
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("test-task-run")).toBeTruthy();
	});

	it("renders all sections when all data is present", async () => {
		const flowRun = createFakeFlowRun({ name: "test-flow-run" });
		const taskRun = createFakeTaskRun({ name: "test-task-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact({ key: "test-key" }),
			flow_run: flowRun,
			task_run: taskRun,
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		// Check for unique elements in each section
		expect(screen.getByText("Key")).toBeTruthy();
		expect(screen.getAllByText("test-key").length).toBeGreaterThan(0);
		expect(screen.getByText("Start time")).toBeTruthy();
		expect(screen.getByText("test-flow-run")).toBeTruthy();
		expect(screen.getByText("test-task-run")).toBeTruthy();
	});

	it("does not render flow run section when flow_run is undefined", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			flow_run: undefined,
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.queryByText("Start time")).toBeNull();
		expect(screen.queryByText("Duration")).toBeNull();
	});

	it("does not render task run section when task_run is undefined", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			task_run: undefined,
		};

		await waitFor(() =>
			render(<MetadataSidebarWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		// Task Run section should not be present (checking for unique elements)
		const taskRunHeaders = screen.queryAllByText("Task Run");
		expect(taskRunHeaders.length).toBe(0);
	});
});
