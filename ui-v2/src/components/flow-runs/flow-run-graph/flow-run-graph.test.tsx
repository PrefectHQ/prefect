import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { ThemeProvider } from "next-themes";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DemoData from "./demo-data.json";
import DemoEvents from "./demo-events.json";
import { FlowRunGraph } from "./flow-run-graph";

vi.mock("@/graphs", () => ({
	emitter: {
		on: vi.fn(() => vi.fn()),
	},
	isArtifactSelection: (selection: { kind: string }) =>
		selection.kind === "artifact",
	isArtifactsSelection: (selection: { kind: string }) =>
		selection.kind === "artifacts",
	isEventSelection: (selection: { kind: string }) => selection.kind === "event",
	isEventsSelection: (selection: { kind: string }) =>
		selection.kind === "events",
	isNodeSelection: (selection: { kind: string }) =>
		selection.kind === "task-run" || selection.kind === "flow-run",
	isStateSelection: (selection: { kind: string }) => selection.kind === "state",
	selectItem: vi.fn(),
	setConfig: vi.fn(),
	start: vi.fn(),
	stop: vi.fn(),
	updateViewportFromDateRange: vi.fn(),
}));

const renderWithProviders = (ui: React.ReactNode) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	return render(
		<QueryClientProvider client={queryClient}>
			<ThemeProvider attribute="class" defaultTheme="light">
				{ui}
			</ThemeProvider>
		</QueryClientProvider>,
	);
};

describe("FlowRunGraph", () => {
	beforeEach(() => {
		server.use(
			http.get(buildApiUrl("/flow_runs/:id/graph-v2"), () => {
				return HttpResponse.json(DemoData);
			}),
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(DemoEvents);
			}),
		);
	});

	it("does not show empty state message when task runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(5);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(<FlowRunGraph flowRunId="test-flow-run" />);

		await waitFor(() => {
			expect(
				screen.queryByText(
					"This flow run did not generate any task or subflow runs",
				),
			).not.toBeInTheDocument();
			expect(
				screen.queryByText(
					"This flow run has not yet generated any task or subflow runs",
				),
			).not.toBeInTheDocument();
		});
	});

	it("does not show empty state message when subflow runs exist", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(3);
			}),
		);

		renderWithProviders(<FlowRunGraph flowRunId="test-flow-run" />);

		await waitFor(() => {
			expect(
				screen.queryByText(
					"This flow run did not generate any task or subflow runs",
				),
			).not.toBeInTheDocument();
			expect(
				screen.queryByText(
					"This flow run has not yet generated any task or subflow runs",
				),
			).not.toBeInTheDocument();
		});
	});

	it("shows terminal empty state message when no nodes exist and state is terminal", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="COMPLETED" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run did not generate any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows non-terminal empty state message when no nodes exist and state is non-terminal", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="RUNNING" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run has not yet generated any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows terminal message for FAILED state", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="FAILED" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run did not generate any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows terminal message for CANCELLED state", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="CANCELLED" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run did not generate any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows terminal message for CRASHED state", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="CRASHED" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run did not generate any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows non-terminal message for PENDING state", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(
			<FlowRunGraph flowRunId="test-flow-run" stateType="PENDING" />,
		);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run has not yet generated any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows non-terminal message when stateType is not provided", async () => {
		server.use(
			http.post(buildApiUrl("/task_runs/count"), () => {
				return HttpResponse.json(0);
			}),
			http.post(buildApiUrl("/flow_runs/count"), () => {
				return HttpResponse.json(0);
			}),
		);

		renderWithProviders(<FlowRunGraph flowRunId="test-flow-run" />);

		await waitFor(() => {
			expect(
				screen.getByText(
					"This flow run has not yet generated any task or subflow runs",
				),
			).toBeInTheDocument();
		});
	});

	describe("artifact selection", () => {
		const renderWithRouter = (ui: React.ReactNode) => {
			const queryClient = new QueryClient({
				defaultOptions: { queries: { retry: false } },
			});
			const rootRoute = createRootRoute();
			const indexRoute = createRoute({
				getParentRoute: () => rootRoute,
				path: "/",
				component: () => (
					<ThemeProvider attribute="class" defaultTheme="light">
						{ui}
					</ThemeProvider>
				),
			});
			const router = createRouter({
				routeTree: rootRoute.addChildren([indexRoute]),
				history: createMemoryHistory({ initialEntries: ["/"] }),
				context: { queryClient },
			});
			return render(
				<QueryClientProvider client={queryClient}>
					<RouterProvider router={router} />
				</QueryClientProvider>,
			);
		};

		beforeEach(() => {
			server.use(
				http.get(buildApiUrl("/artifacts/:id"), () => {
					return HttpResponse.json({
						id: "artifact-123",
						key: "my-artifact",
						type: "markdown",
						description: null,
						data: "# Report",
						created: "2024-01-15T10:30:00Z",
						updated: "2024-01-15T10:30:00Z",
						flow_run_id: "test-flow-run",
						task_run_id: null,
					});
				}),
			);
		});

		it("opens the artifact drawer when a single artifact is selected", async () => {
			renderWithRouter(
				<FlowRunGraph
					flowRunId="test-flow-run"
					selected={{ kind: "artifact", id: "artifact-123" }}
				/>,
			);

			expect(await screen.findByText("Artifact Details")).toBeInTheDocument();
			expect(await screen.findByText("my-artifact")).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: /open artifact/i }),
			).toHaveAttribute("href", "/artifacts/artifact/artifact-123");
		});

		it("clears the selection when the artifact drawer is closed", async () => {
			const user = userEvent.setup();
			const onSelectedChange = vi.fn();

			renderWithRouter(
				<FlowRunGraph
					flowRunId="test-flow-run"
					selected={{ kind: "artifact", id: "artifact-123" }}
					onSelectedChange={onSelectedChange}
				/>,
			);

			await screen.findByText("my-artifact");
			await user.click(screen.getByRole("button", { name: "Close" }));

			await waitFor(() => {
				expect(onSelectedChange).toHaveBeenCalledWith(undefined);
			});
		});
	});
});
