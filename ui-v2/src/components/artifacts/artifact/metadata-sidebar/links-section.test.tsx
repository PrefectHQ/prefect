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
import { LinksSection } from "./links-section";

type LinksSectionProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
};

const LinksSectionWrapper = (props: LinksSectionProps) => {
	const rootRoute = createRootRoute({
		component: () => <LinksSection {...props} />,
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

describe("LinksSection", () => {
	it("renders artifact key link", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact({ key: "test-artifact-key" }),
		};

		await waitFor(() =>
			render(<LinksSectionWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Artifact")).toBeTruthy();
		expect(screen.getByText("test-artifact-key")).toBeTruthy();
	});

	it("renders flow run link", async () => {
		const flowRun = createFakeFlowRun({ name: "test-flow-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			flow_run: flowRun,
		};

		await waitFor(() =>
			render(<LinksSectionWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Flow Run")).toBeTruthy();
		expect(screen.getByText("test-flow-run")).toBeTruthy();
	});

	it("renders task run link", async () => {
		const taskRun = createFakeTaskRun({ name: "test-task-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact(),
			task_run: taskRun,
		};

		await waitFor(() =>
			render(<LinksSectionWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Task Run")).toBeTruthy();
		expect(screen.getByText("test-task-run")).toBeTruthy();
	});

	it("renders all links when all data is present", async () => {
		const flowRun = createFakeFlowRun({ name: "test-flow-run" });
		const taskRun = createFakeTaskRun({ name: "test-task-run" });
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact({ key: "test-artifact-key" }),
			flow_run: flowRun,
			task_run: taskRun,
		};

		await waitFor(() =>
			render(<LinksSectionWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Artifact")).toBeTruthy();
		expect(screen.getByText("test-artifact-key")).toBeTruthy();
		expect(screen.getByText("Flow Run")).toBeTruthy();
		expect(screen.getByText("test-flow-run")).toBeTruthy();
		expect(screen.getByText("Task Run")).toBeTruthy();
		expect(screen.getByText("test-task-run")).toBeTruthy();
	});

	it("returns null when no links are present", async () => {
		const artifact: ArtifactWithFlowRunAndTaskRun = {
			...createFakeArtifact({ key: null }),
			flow_run: undefined,
			task_run: undefined,
		};

		const { container } = await waitFor(() =>
			render(<LinksSectionWrapper artifact={artifact} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(container.textContent).toBe("");
	});
});
