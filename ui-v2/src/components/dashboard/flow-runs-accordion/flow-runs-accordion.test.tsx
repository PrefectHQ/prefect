import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import type { FlowRunsFilter } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import { createFakeFlow, createFakeFlowRun, createFakeState } from "@/mocks";
import { FlowRunStateTypeEmpty } from "./flow-run-state-type-empty";
import { FlowRunsAccordionContent } from "./flow-runs-accordion-content";
import { FlowRunsAccordionHeader } from "./flow-runs-accordion-header";
import { FlowRunsAccordion, type FlowRunsAccordionProps } from "./index";

const createRouterWithComponent = (component: React.ReactNode) => {
	const rootRoute = createRootRoute({
		component: () => component,
	});
	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
};

const FlowRunsAccordionRouter = (props: FlowRunsAccordionProps) => {
	const router = createRouterWithComponent(
		<Suspense fallback={<div>Loading...</div>}>
			<FlowRunsAccordion {...props} />
		</Suspense>,
	);
	return <RouterProvider router={router} />;
};

const FlowRunsAccordionHeaderRouter = ({
	flow,
	filter,
}: {
	flow: Flow;
	filter: FlowRunsFilter;
}) => {
	const router = createRouterWithComponent(
		<FlowRunsAccordionHeader flow={flow} filter={filter} />,
	);
	return <RouterProvider router={router} />;
};

const FlowRunsAccordionContentRouter = ({
	flowId,
	filter,
}: {
	flowId: string;
	filter?: FlowRunsFilter;
}) => {
	const router = createRouterWithComponent(
		<Suspense fallback={<div>Loading...</div>}>
			<FlowRunsAccordionContent flowId={flowId} filter={filter} />
		</Suspense>,
	);
	return <RouterProvider router={router} />;
};

describe("FlowRunStateTypeEmpty", () => {
	it("renders empty state message for failed state type", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["FAILED"]} />);

		expect(
			screen.getByText("You currently have 0 failed runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for multiple state types", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["FAILED", "CRASHED"]} />);

		expect(
			screen.getByText("You currently have 0 failed or crashed runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for scheduled state type as late", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["SCHEDULED"]} />);

		expect(
			screen.getByText("You currently have 0 late runs."),
		).toBeInTheDocument();
	});

	it("renders empty state message for running state types", () => {
		render(<FlowRunStateTypeEmpty stateTypes={["RUNNING", "PENDING"]} />);

		expect(
			screen.getByText("You currently have 0 running or pending runs."),
		).toBeInTheDocument();
	});

	it("renders bad terminal image for failed state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["FAILED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 157 128");
	});

	it("renders bad terminal image for crashed state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["CRASHED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 157 128");
	});

	it("renders live image for running state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["RUNNING"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 129 128");
	});

	it("renders live image for pending state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["PENDING"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 129 128");
	});

	it("renders good terminal image for completed state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["COMPLETED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 111 110");
	});

	it("renders awaiting image for scheduled state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["SCHEDULED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 92 128");
	});

	it("renders awaiting image for paused state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["PAUSED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).toBeInTheDocument();
		expect(svg).toHaveAttribute("viewBox", "0 0 92 128");
	});

	it("renders no image for cancelled state type", () => {
		const { container } = render(
			<FlowRunStateTypeEmpty stateTypes={["CANCELLED"]} />,
		);

		const svg = container.querySelector("svg");
		expect(svg).not.toBeInTheDocument();
	});
});

describe("FlowRunsAccordion", () => {
	it("renders empty state when there are no flow runs", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		render(<FlowRunsAccordionRouter stateTypes={["FAILED"]} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(
				screen.getByText("You currently have 0 failed runs."),
			).toBeInTheDocument();
		});
	});

	it("renders accordion with flow runs grouped by flow", async () => {
		const flow1 = createFakeFlow({ id: "flow-1", name: "Test Flow 1" });
		const flow2 = createFakeFlow({ id: "flow-2", name: "Test Flow 2" });
		const flowRun1 = createFakeFlowRun({
			id: "run-1",
			flow_id: "flow-1",
			state_type: "FAILED",
		});
		const flowRun2 = createFakeFlowRun({
			id: "run-2",
			flow_id: "flow-2",
			state_type: "FAILED",
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([flowRun1, flowRun2]);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([flow1, flow2]);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(1);
			}),
		);

		render(<FlowRunsAccordionRouter stateTypes={["FAILED"]} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Test Flow 1")).toBeInTheDocument();
		});

		await waitFor(() => {
			expect(screen.getByText("Test Flow 2")).toBeInTheDocument();
		});
	});
});

describe("FlowRunsAccordionHeader", () => {
	it("renders flow name as a link", async () => {
		const flow = createFakeFlow({ id: "flow-1", name: "My Test Flow" });
		const flowRun = createFakeFlowRun({
			id: "run-1",
			flow_id: "flow-1",
			start_time: new Date().toISOString(),
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(5);
			}),
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([flowRun]);
			}),
		);

		render(
			<FlowRunsAccordionHeaderRouter
				flow={flow}
				filter={{ sort: "START_TIME_DESC", offset: 0 }}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByText("My Test Flow");
			expect(link).toBeInTheDocument();
			expect(link.closest("a")).toHaveAttribute("href", "/flows/flow/flow-1");
		});
	});

	it("renders flow run count", async () => {
		const flow = createFakeFlow({ id: "flow-1", name: "Test Flow" });

		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(42);
			}),
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		render(
			<FlowRunsAccordionHeaderRouter
				flow={flow}
				filter={{ sort: "START_TIME_DESC", offset: 0 }}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("42")).toBeInTheDocument();
		});
	});

	it("renders relative time for last flow run", async () => {
		const flow = createFakeFlow({ id: "flow-1", name: "Test Flow" });
		const recentDate = new Date();
		recentDate.setMinutes(recentDate.getMinutes() - 5);
		const flowRun = createFakeFlowRun({
			id: "run-1",
			flow_id: "flow-1",
			start_time: recentDate.toISOString(),
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(1);
			}),
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([flowRun]);
			}),
		);

		render(
			<FlowRunsAccordionHeaderRouter
				flow={flow}
				filter={{ sort: "START_TIME_DESC", offset: 0 }}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText(/minutes? ago/i)).toBeInTheDocument();
		});
	});
});

describe("FlowRunsAccordionContent", () => {
	it("renders flow runs with state badge and details", async () => {
		const flowRun = createFakeFlowRun({
			id: "run-1",
			name: "test-run-name",
			flow_id: "flow-1",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				id: "state-1",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-15T10:30:00Z",
			}),
			start_time: "2024-01-15T10:30:00Z",
			estimated_run_time: 120,
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [flowRun],
					count: 1,
					pages: 1,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 5 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("test-run-name")).toBeInTheDocument();
		});

		expect(screen.getByText("Completed")).toBeInTheDocument();
	});

	it("renders flow run name as a link", async () => {
		const flowRun = createFakeFlowRun({
			id: "run-123",
			name: "clickable-run",
			flow_id: "flow-1",
			state_type: "RUNNING",
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [flowRun],
					count: 1,
					pages: 1,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-123": 3 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const link = screen.getByText("clickable-run");
			expect(link.closest("a")).toHaveAttribute(
				"href",
				"/runs/flow-run/run-123",
			);
		});
	});

	it("renders pagination when there are multiple pages", async () => {
		const flowRuns = [
			createFakeFlowRun({ id: "run-1", name: "Run 1", flow_id: "flow-1" }),
			createFakeFlowRun({ id: "run-2", name: "Run 2", flow_id: "flow-1" }),
			createFakeFlowRun({ id: "run-3", name: "Run 3", flow_id: "flow-1" }),
		];

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: flowRuns,
					count: 10,
					pages: 4,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 2, "run-2": 3, "run-3": 1 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Page 1 of 4")).toBeInTheDocument();
		});
	});

	it("does not render pagination when there is only one page", async () => {
		const flowRun = createFakeFlowRun({
			id: "run-1",
			name: "Single Run",
			flow_id: "flow-1",
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [flowRun],
					count: 1,
					pages: 1,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 0 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Single Run")).toBeInTheDocument();
		});

		expect(screen.queryByText(/Page \d+ of \d+/)).not.toBeInTheDocument();
	});

	it("navigates between pages when clicking pagination buttons", async () => {
		const user = userEvent.setup();
		const page1Runs = [
			createFakeFlowRun({ id: "run-1", name: "Page 1 Run", flow_id: "flow-1" }),
		];
		const page2Runs = [
			createFakeFlowRun({ id: "run-4", name: "Page 2 Run", flow_id: "flow-1" }),
		];

		let currentPage = 1;
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				const runs = currentPage === 1 ? page1Runs : page2Runs;
				return HttpResponse.json({
					results: runs,
					count: 6,
					pages: 2,
					page: currentPage,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 1, "run-4": 2 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
		});

		currentPage = 2;
		const nextButton = screen.getByRole("button", { name: /next/i });
		await user.click(nextButton);

		await waitFor(() => {
			expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
		});
	});

	it("renders duration for flow runs with estimated_run_time", async () => {
		const flowRun = createFakeFlowRun({
			id: "run-1",
			name: "Timed Run",
			flow_id: "flow-1",
			estimated_run_time: 3661,
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [flowRun],
					count: 1,
					pages: 1,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 4 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Timed Run")).toBeInTheDocument();
		});

		// Duration is formatted as "X.XX seconds" by FlowRunDuration component
		expect(screen.getByText(/seconds/i)).toBeInTheDocument();
	});

	it("renders parameters and task runs for flow runs", async () => {
		const flowRun = createFakeFlowRun({
			id: "run-1",
			name: "test-run",
			flow_id: "flow-1",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
			parameters: { key: "value" },
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [flowRun],
					count: 1,
					pages: 1,
					page: 1,
					limit: 3,
				});
			}),
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
				return HttpResponse.json({ "run-1": 5 });
			}),
		);

		render(<FlowRunsAccordionContentRouter flowId="flow-1" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("test-run")).toBeInTheDocument();
		});

		expect(screen.getByText("1 Parameter")).toBeInTheDocument();
		await waitFor(() => {
			expect(screen.getByText("5 Task runs")).toBeInTheDocument();
		});
	});
});
