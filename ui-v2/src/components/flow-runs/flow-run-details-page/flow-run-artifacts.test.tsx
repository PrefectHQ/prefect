import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeArtifact, createFakeFlowRun } from "@/mocks";
import { FlowRunArtifacts } from "./flow-run-artifacts";

const FlowRunArtifactsRouter = ({
	flowRun,
}: {
	flowRun: ReturnType<typeof createFakeFlowRun>;
}) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunArtifacts flowRun={flowRun} />,
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

describe("FlowRunArtifacts", () => {
	const mockFlowRun = createFakeFlowRun();
	const mockArtifacts = Array.from({ length: 3 }, () =>
		createFakeArtifact({
			flow_run_id: mockFlowRun.id,
		}),
	);

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json(mockArtifacts);
			}),
		);
	});

	it("renders empty state when no artifacts are present", async () => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		render(<FlowRunArtifactsRouter flowRun={mockFlowRun} />, {
			wrapper: createWrapper(),
		});

		expect(
			await screen.findByText(/This flow run did not produce any artifacts/),
		).toBeInTheDocument();
		expect(screen.getByRole("link", { name: /documentation/ })).toHaveAttribute(
			"href",
			"https://docs.prefect.io/v3/develop/artifacts",
		);
	});

	it("switches between grid and list views", async () => {
		render(<FlowRunArtifactsRouter flowRun={mockFlowRun} />, {
			wrapper: createWrapper(),
		});

		const gridButton = await screen.findByLabelText(/Grid view/i);
		const listButton = await screen.findByLabelText(/List view/i);
		const grid = await screen.findByTestId("flow-run-artifacts-grid");
		expect(grid).toHaveClass("grid-cols-1 lg:grid-cols-2 xl:grid-cols-3");

		fireEvent.click(listButton);
		expect(grid).toHaveClass("grid-cols-1");

		fireEvent.click(gridButton);
		expect(grid).toHaveClass("grid-cols-1 lg:grid-cols-2 xl:grid-cols-3");
	});

	it("uses correct query parameters for fetching artifacts", async () => {
		let requestBody: unknown;
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), async ({ request }) => {
				requestBody = await request.json();
				return HttpResponse.json(mockArtifacts);
			}),
		);

		render(<FlowRunArtifactsRouter flowRun={mockFlowRun} />, {
			wrapper: createWrapper(),
		});

		await screen.findByText(mockArtifacts[0].key as string);

		expect(requestBody).toEqual({
			artifacts: {
				operator: "and_",
				flow_run_id: {
					any_: [mockFlowRun.id],
				},
				type: {
					not_any_: ["result"],
				},
			},
			sort: "ID_DESC",
			offset: 0,
		});
	});
});
