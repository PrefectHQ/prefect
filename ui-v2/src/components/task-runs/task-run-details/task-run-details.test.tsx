import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeArtifact, createFakeTaskRun } from "@/mocks";
import { TaskRunDetails, type TaskRunDetailsProps } from "./task-run-details";

// Wraps component in test with a Tanstack router provider
const TaskRunDetailsRouter = (props: TaskRunDetailsProps) => {
	const rootRoute = createRootRoute({
		component: () => <TaskRunDetails {...props} />,
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

describe("TaskRunDetails", () => {
	it("should display flow run link", async () => {
		const taskRun = createFakeTaskRun({
			name: "test-task-name",
			flow_run_name: "test-flow-name",
			flow_run_id: "test-flow-run-id",
		});
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={taskRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("test-flow-name")).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: /test-flow-name/i }),
		).toHaveAttribute("href", "/runs/flow-run/test-flow-run-id");
	});

	it("should display task run ID", async () => {
		const taskRun = createFakeTaskRun({ id: "test-task-id" });
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={taskRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("test-task-id")).toBeInTheDocument();
	});

	it("should display start time", async () => {
		const startTime = new Date().toISOString();
		const taskRun = createFakeTaskRun({
			start_time: startTime,
		});
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={taskRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Start Time").nextSibling).toBeInTheDocument();
	});

	it("should display task tags", async () => {
		const taskRun = createFakeTaskRun({
			tags: ["tag1", "tag2", "tag3"],
		});
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={taskRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
		expect(screen.getByText("tag3")).toBeInTheDocument();
	});

	it("should display empty state when no taskRun is provided", async () => {
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={null} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(
			screen.getByText("No task run details available"),
		).toBeInTheDocument();
	});

	it("should display task configuration section", async () => {
		const taskRun = createFakeTaskRun();
		const screen = await waitFor(() =>
			render(<TaskRunDetailsRouter taskRun={taskRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(screen.getByText("Task configuration")).toBeInTheDocument();
		expect(screen.getByText("Version")).toBeInTheDocument();
		expect(screen.getByText("Retries")).toBeInTheDocument();
		expect(screen.getByText("Retry Delay")).toBeInTheDocument();
	});

	it("should display result artifact when present", async () => {
		const taskRunId = "test-task-run-id";
		const resultArtifact = createFakeArtifact({
			task_run_id: taskRunId,
			type: "result",
			description: "Test result description",
		});

		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([resultArtifact]);
			}),
		);

		const taskRun = createFakeTaskRun({ id: taskRunId });
		const screen = render(<TaskRunDetailsRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Result")).toBeInTheDocument();
		});
		await waitFor(() => {
			expect(screen.getByText("Test result description")).toBeInTheDocument();
		});
	});

	it("should not display result section when no artifact exists", async () => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const taskRun = createFakeTaskRun({ id: "test-task-run-id" });
		const screen = render(<TaskRunDetailsRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Task Run ID")).toBeInTheDocument();
		});
		expect(screen.queryByText("Result")).not.toBeInTheDocument();
	});

	it("should not display result section when artifact has no description", async () => {
		const taskRunId = "test-task-run-id";
		const resultArtifact = createFakeArtifact({
			task_run_id: taskRunId,
			type: "result",
			description: null,
		});

		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([resultArtifact]);
			}),
		);

		const taskRun = createFakeTaskRun({ id: taskRunId });
		const screen = render(<TaskRunDetailsRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Task Run ID")).toBeInTheDocument();
		});
		expect(screen.queryByText("Result")).not.toBeInTheDocument();
	});

	it("should render markdown content in result artifact", async () => {
		const taskRunId = "test-task-run-id";
		const resultArtifact = createFakeArtifact({
			task_run_id: taskRunId,
			type: "result",
			description: "**Bold text** and *italic text*",
		});

		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([resultArtifact]);
			}),
		);

		const taskRun = createFakeTaskRun({ id: taskRunId });
		const screen = render(<TaskRunDetailsRouter taskRun={taskRun} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Result")).toBeInTheDocument();
		});
		await waitFor(() => {
			expect(screen.getByText("Bold text")).toBeInTheDocument();
		});
		expect(screen.getByText("italic text")).toBeInTheDocument();
	});
});
