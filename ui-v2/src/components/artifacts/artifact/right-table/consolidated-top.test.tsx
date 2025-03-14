import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
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
import { describe, expect, it } from "vitest";
import { ConsolidatedTop, ConsolidatedTopProps } from "./consolidated-top";

// Wraps component in test with a Tanstack router provider
const ConsolidatedTopWrapper = (props: ConsolidatedTopProps) => {
	const rootRoute = createRootRoute({
		component: () => <ConsolidatedTop {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	// @ts-expect-error - Type error from using a test router
	return <RouterProvider router={router} />;
};

void describe("Consolidated top section on right bar of details page", () => {
	const fakeArtifact = createFakeArtifact();
	const fakeTaskRun = createFakeTaskRun();
	const fakeFlowRun = createFakeFlowRun();

	const fakeArtifactWithMetadata: ArtifactWithFlowRunAndTaskRun = {
		...fakeArtifact,
		flow_run: fakeFlowRun,
		task_run: fakeTaskRun,
	};

	it("renders consolidated top section with artifact key", () => {
		const { getByText } = render(
			<ConsolidatedTopWrapper artifact={fakeArtifactWithMetadata} />,
		);

		expect(getByText("Artifact")).toBeTruthy();
		expect(getByText(fakeArtifact.key ?? "")).toBeTruthy();
	});

	it("renders consolidated top section with flow run name", () => {
		const { getByText } = render(
			<ConsolidatedTopWrapper artifact={fakeArtifactWithMetadata} />,
		);

		expect(getByText("Flow Run")).toBeTruthy();
		expect(getByText(fakeFlowRun.name ?? "")).toBeTruthy();
	});

	it("renders consolidated top section with task run name", () => {
		const { getByText } = render(
			<ConsolidatedTopWrapper artifact={fakeArtifactWithMetadata} />,
		);

		expect(getByText("Task Run")).toBeTruthy();
		expect(getByText(fakeTaskRun.name ?? "")).toBeTruthy();
	});
});
