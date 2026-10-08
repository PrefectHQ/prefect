import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphArtifactDrawer } from "./flow-run-graph-artifact-drawer";

const renderDrawer = (
	props: Parameters<typeof FlowRunGraphArtifactDrawer>[0],
) => {
	const rootRoute = createRootRoute();
	const indexRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: () => <FlowRunGraphArtifactDrawer {...props} />,
	});
	const router = createRouter({
		routeTree: rootRoute.addChildren([indexRoute]),
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return render(<RouterProvider router={router} />, {
		wrapper: createWrapper(),
	});
};

describe("FlowRunGraphArtifactDrawer", () => {
	const mockArtifactResponse = {
		id: "artifact-123",
		key: "my-artifact" as string | null,
		type: "result" as string | null,
		description: "A test artifact description" as string | null,
		created: "2024-01-15T10:30:00Z",
		data: { value: 42, status: "success" } as unknown,
		flow_run_id: "flow-run-123",
		task_run_id: null,
		updated: "2024-01-15T10:30:00Z",
	};

	const setupMockServer = (
		response: typeof mockArtifactResponse = mockArtifactResponse,
	) => {
		server.use(
			http.get(buildApiUrl("/artifacts/:id"), () => {
				return HttpResponse.json(response);
			}),
		);
	};

	it("renders when artifactId is provided", async () => {
		setupMockServer();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("Artifact Details")).toBeInTheDocument();
		expect(await screen.findByText("my-artifact")).toBeInTheDocument();
	});

	it("does not render when artifactId is null", () => {
		const onClose = vi.fn();

		render(<FlowRunGraphArtifactDrawer artifactId={null} onClose={onClose} />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByText("Artifact Details")).not.toBeInTheDocument();
	});

	it("displays artifact details correctly", async () => {
		setupMockServer();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("my-artifact")).toBeInTheDocument();
		expect(screen.getByText("result")).toBeInTheDocument();
		expect(screen.getByText("A test artifact description")).toBeInTheDocument();
		expect(screen.getByText("Key")).toBeInTheDocument();
		expect(screen.getByText("Type")).toBeInTheDocument();
		expect(screen.getByText("Description")).toBeInTheDocument();
		expect(screen.getByText("Created")).toBeInTheDocument();
		expect(screen.getByText("Data")).toBeInTheDocument();
	});

	it("displays artifact data as JSON", async () => {
		setupMockServer();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		await screen.findByText("my-artifact");
		const dataElement = screen.getByText(/value/);
		expect(dataElement).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		await screen.findByText("my-artifact");

		const closeButton = screen.getByRole("button", { name: "Close" });
		await user.click(closeButton);

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("shows loading state with skeleton", async () => {
		server.use(
			http.get(buildApiUrl("/artifacts/:id"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(mockArtifactResponse);
			}),
		);
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("Artifact Details")).toBeInTheDocument();
		const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
		expect(skeletons.length).toBeGreaterThan(0);

		expect(await screen.findByText("my-artifact")).toBeInTheDocument();
	});

	it("shows 'Unnamed' for artifacts without keys", async () => {
		setupMockServer({ ...mockArtifactResponse, key: null });
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("Unnamed")).toBeInTheDocument();
	});

	it("does not show type section when type is null", async () => {
		setupMockServer({ ...mockArtifactResponse, type: null });
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		await screen.findByText("my-artifact");
		expect(screen.queryByText("Type")).not.toBeInTheDocument();
	});

	it("does not show description section when description is null", async () => {
		setupMockServer({ ...mockArtifactResponse, description: null });
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		await screen.findByText("my-artifact");
		expect(screen.queryByText("Description")).not.toBeInTheDocument();
	});

	it("displays string data directly without JSON formatting", async () => {
		setupMockServer({ ...mockArtifactResponse, data: "Simple string data" });
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("Simple string data")).toBeInTheDocument();
	});

	it("calls onClose when pressing Escape", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		await screen.findByText("my-artifact");

		await user.keyboard("{Escape}");

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("links to the artifact detail page", async () => {
		setupMockServer();
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		const link = await screen.findByRole("link", { name: /open artifact/i });
		expect(link).toHaveAttribute("href", "/artifacts/artifact/artifact-123");
		expect(link).toHaveAttribute("target", "_blank");
	});

	it("renders markdown artifacts as markdown", async () => {
		setupMockServer({
			...mockArtifactResponse,
			type: "markdown",
			data: "# Hello from markdown",
		});
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByTestId("markdown-display")).toBeInTheDocument();
		expect(
			await screen.findByRole("heading", { name: "Hello from markdown" }),
		).toBeInTheDocument();
	});

	it("renders table artifacts with array data", async () => {
		setupMockServer({
			...mockArtifactResponse,
			type: "table",
			data: [
				{ metric: "latency", value: 120 },
				{ metric: "throughput", value: 1500 },
			],
		});
		const onClose = vi.fn();

		renderDrawer({ artifactId: "artifact-123", onClose });

		expect(await screen.findByText("latency")).toBeInTheDocument();
		expect(screen.getByText("throughput")).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: /open artifact/i }),
		).toBeInTheDocument();
	});
});
