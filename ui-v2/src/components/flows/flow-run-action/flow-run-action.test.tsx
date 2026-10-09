import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
} from "@/mocks";
import { FlowDeploymentCount } from "../cells";
import { FlowRunAction } from "./flow-run-action";

beforeAll(() => {
	// Polyfill scrollIntoView used by cmdk
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		configurable: true,
		value: vi.fn(),
	});
});

const FlowRunActionRouter = ({ children }: { children: ReactNode }) => {
	const rootRoute = createRootRoute({
		component: () => (
			<>
				<Toaster />
				{children}
			</>
		),
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

const renderAction = async (children: ReactNode) => {
	await waitFor(() =>
		render(<FlowRunActionRouter>{children}</FlowRunActionRouter>, {
			wrapper: createWrapper(),
		}),
	);
};

const mockCount = (flowId: string, count: number) => {
	const countDeployments = vi.fn();
	server.use(
		http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
			countDeployments();
			return HttpResponse.json({ [flowId]: count });
		}),
	);
	return countDeployments;
};

describe("FlowRunAction availability", () => {
	it("shows a visible Run button while the count is loading", async () => {
		const flow = createFakeFlow();
		server.use(
			http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
				return new Promise(() => {});
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);

		const button = screen.getByRole("button", { name: /run/i });
		expect(button).toBeVisible();
		expect(button).toBeDisabled();
		await waitFor(() =>
			expect(button).toHaveAccessibleDescription("Checking for deployments"),
		);
	});

	it("disables Run with a retry reason when the count request fails", async () => {
		const flow = createFakeFlow();
		server.use(
			http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
				return HttpResponse.error();
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);

		const button = screen.getByRole("button", { name: /run/i });
		await waitFor(() =>
			expect(button).toHaveAccessibleDescription(
				"Could not check deployments. Refresh to retry.",
			),
		);
		expect(button).toBeDisabled();
	});

	it("disables Run with a deployment prerequisite reason when the count is zero", async () => {
		const flow = createFakeFlow();
		mockCount(flow.id, 0);
		await renderAction(<FlowRunAction flow={flow} />);

		const button = screen.getByRole("button", { name: /run/i });
		await waitFor(() =>
			expect(button).toHaveAccessibleDescription(
				"Create a deployment to run this flow from the UI.",
			),
		);
		expect(button).toBeDisabled();
	});

	it("enables Run when the flow has deployments", async () => {
		const flow = createFakeFlow();
		mockCount(flow.id, 2);
		await renderAction(<FlowRunAction flow={flow} />);

		await waitFor(() =>
			expect(screen.getByRole("button", { name: /run/i })).toBeEnabled(),
		);
	});

	it("shares the count query with FlowDeploymentCount", async () => {
		const flow = createFakeFlow();
		const countDeployments = mockCount(flow.id, 3);
		await renderAction(
			<>
				<FlowDeploymentCount row={{ original: flow }} />
				<FlowRunAction flow={flow} />
			</>,
		);

		await waitFor(() =>
			expect(screen.getByRole("button", { name: /run/i })).toBeEnabled(),
		);
		expect(countDeployments).toHaveBeenCalledTimes(1);
	});
});

const mockPaginate = (
	responses: {
		results: ReturnType<typeof createFakeDeployment>[];
		count: number;
	},
	bodies: Record<string, unknown>[],
) => {
	server.use(
		http.post(buildApiUrl("/deployments/paginate"), async ({ request }) => {
			const body = (await request.json()) as Record<string, unknown> & {
				page: number;
				limit: number;
			};
			bodies.push(body);
			const start = (body.page - 1) * body.limit;
			const pageResults = responses.results.slice(start, start + body.limit);
			return HttpResponse.json({
				results: pageResults,
				count: responses.count,
				page: body.page,
				pages: Math.max(1, Math.ceil(responses.count / body.limit)),
				limit: body.limit,
			});
		}),
	);
};

const openDialog = async () => {
	const user = userEvent.setup();
	await waitFor(() =>
		expect(screen.getByRole("button", { name: /run/i })).toBeEnabled(),
	);
	await user.click(screen.getByRole("button", { name: /run/i }));
	return user;
};

describe("FlowRunAction dialog", () => {
	it("opens a dialog titled with the flow name", async () => {
		const flow = createFakeFlow();
		mockCount(flow.id, 2);
		const bodies: Record<string, unknown>[] = [];
		mockPaginate({ results: [], count: 2 }, bodies);
		await renderAction(<FlowRunAction flow={flow} />);
		await openDialog();

		expect(
			await screen.findByRole("dialog", {
				name: new RegExp(`Run ${flow.name}`),
			}),
		).toBeVisible();
	});

	it("preselects the only deployment without creating a run", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({ flow_id: flow.id });
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		await openDialog();

		await screen.findByRole("dialog");
		expect(
			await screen.findByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent(deployment.name);
		expect(createFlowRun).not.toHaveBeenCalled();
	});

	it("requires an explicit choice when the flow has multiple deployments", async () => {
		const flow = createFakeFlow();
		const deployments = [
			createFakeDeployment({ flow_id: flow.id }),
			createFakeDeployment({ flow_id: flow.id }),
		];
		mockCount(flow.id, 2);
		mockPaginate({ results: deployments, count: 2 }, []);
		await renderAction(<FlowRunAction flow={flow} />);
		await openDialog();

		await screen.findByRole("dialog");
		expect(
			await screen.findByText("Select a deployment to run it."),
		).toBeVisible();
	});

	it("lets the user pick a deployment on a later page", async () => {
		const flow = createFakeFlow();
		const deployments = Array.from({ length: 12 }, (_, i) =>
			createFakeDeployment({
				flow_id: flow.id,
				name: `dep-${String(i).padStart(2, "0")}`,
			}),
		);
		const target = deployments[11];
		mockCount(flow.id, 12);
		mockPaginate({ results: deployments, count: 12 }, []);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await screen.findByRole("dialog");
		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("button", { name: "Next" }));
		await user.click(await screen.findByRole("option", { name: target.name }));

		expect(
			screen.getByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent(target.name);
	});

	it("shows a no-matches message for a search with zero results", async () => {
		const flow = createFakeFlow();
		const deployments = [
			createFakeDeployment({ flow_id: flow.id }),
			createFakeDeployment({ flow_id: flow.id }),
		];
		mockCount(flow.id, 2);
		server.use(
			http.post(buildApiUrl("/deployments/paginate"), async ({ request }) => {
				const body = (await request.json()) as {
					deployments?: { name?: { like_?: string } };
				};
				const search = body.deployments?.name?.like_;
				const results = search ? [] : deployments;
				return HttpResponse.json({
					results,
					count: results.length,
					page: 1,
					pages: 1,
					limit: 10,
				});
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.type(
			screen.getByPlaceholderText("Search deployments..."),
			"zzz",
		);

		expect(
			await screen.findByText("No deployments match your search"),
		).toBeVisible();
	});

	it("sends the flow filter on every paginate request", async () => {
		const flow = createFakeFlow();
		const deployments = Array.from({ length: 15 }, (_, i) =>
			createFakeDeployment({ flow_id: flow.id, name: `dep-${i}` }),
		);
		mockCount(flow.id, 15);
		const bodies: Record<string, unknown>[] = [];
		mockPaginate({ results: deployments, count: 15 }, bodies);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("button", { name: "Next" }));
		await screen.findByRole("option", { name: "dep-14" });

		expect(bodies.length).toBeGreaterThanOrEqual(2);
		for (const body of bodies) {
			expect(body).toMatchObject({
				flows: { operator: "and_", id: { any_: [flow.id] } },
				sort: "NAME_ASC",
			});
		}
	});

	it("isolates selections per flow", async () => {
		const flowA = createFakeFlow();
		const flowB = createFakeFlow();
		const depA = createFakeDeployment({
			flow_id: flowA.id,
			name: "dep-a",
		});
		const depB = createFakeDeployment({
			flow_id: flowB.id,
			name: "dep-b",
		});
		server.use(
			http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
				HttpResponse.json({ [flowA.id]: 2, [flowB.id]: 2 }),
			),
			http.post(buildApiUrl("/deployments/paginate"), async ({ request }) => {
				const body = (await request.json()) as {
					flows?: { id?: { any_?: string[] } };
				};
				const flowId = body.flows?.id?.any_?.[0];
				const results =
					flowId === flowA.id
						? [depA, createFakeDeployment({ flow_id: flowA.id })]
						: [depB, createFakeDeployment({ flow_id: flowB.id })];
				return HttpResponse.json({
					results,
					count: 2,
					page: 1,
					pages: 1,
					limit: 10,
				});
			}),
		);
		await renderAction(
			<>
				<FlowRunAction flow={flowA} />
				<FlowRunAction flow={flowB} />
			</>,
		);
		const user = userEvent.setup();

		await waitFor(() =>
			expect(screen.getAllByRole("button", { name: /run/i })).toHaveLength(2),
		);
		const [runA, runB] = screen.getAllByRole("button", { name: /run/i });
		await waitFor(() => expect(runA).toBeEnabled());
		await waitFor(() => expect(runB).toBeEnabled());

		await user.click(runA);
		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("option", { name: "dep-a" }));
		await user.keyboard("{Escape}");
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);

		await user.click(runB);
		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		expect(
			await screen.findByRole("option", { name: "dep-b" }),
		).toBeInTheDocument();
		expect(
			screen.queryByRole("option", { name: "dep-a" }),
		).not.toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent("Select a deployment");
	});

	it("creates nothing when the dialog is cancelled", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({ flow_id: flow.id });
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await screen.findByRole("dialog");
		await user.keyboard("{Escape}");
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);
		expect(createFlowRun).not.toHaveBeenCalled();
	});

	it("runs the explicitly selected deployment and closes the dialog on success", async () => {
		const flow = createFakeFlow();
		const deployments = [
			createFakeDeployment({ flow_id: flow.id, name: "first-dep" }),
			createFakeDeployment({ flow_id: flow.id, name: "second-dep" }),
		];
		const target = deployments[1];
		mockCount(flow.id, 2);
		mockPaginate({ results: deployments, count: 2 }, []);
		const createFlowRun = vi.fn();
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/create_flow_run"),
				({ params }) => {
					createFlowRun(params.id);
					return HttpResponse.json(createFakeFlowRun());
				},
			),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("option", { name: "second-dep" }));
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);

		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(1));
		expect(createFlowRun).toHaveBeenCalledWith(target.id);
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);
		expect(
			await screen.findByRole("button", { name: /view run/i }),
		).toBeVisible();
	});

	it("keeps the dialog open and the selection after a quick run failure", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({
			flow_id: flow.id,
			name: "only-dep",
		});
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		let fail = true;
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				if (fail) {
					return HttpResponse.error();
				}
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Select a deployment" }),
			).toHaveTextContent("only-dep"),
		);
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);

		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(1));
		expect(screen.getByRole("dialog")).toBeVisible();
		expect(
			screen.getByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent("only-dep");

		fail = false;
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);
		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(2));
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);
	});

	it("creates exactly one run for repeated quick run attempts while pending", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({ flow_id: flow.id });
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		let resolveRequest: (() => void) | undefined;
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), async () => {
				createFlowRun();
				await new Promise<void>((resolve) => {
					resolveRequest = resolve;
				});
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Select a deployment" }),
			).toHaveTextContent(deployment.name),
		);
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);
		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(1));

		// The trigger is disabled while the mutation is pending, so repeated
		// attempts cannot dispatch another request.
		await waitFor(() => {
			const trigger = screen
				.getAllByRole("button")
				.find((b) => b.getAttribute("aria-haspopup") === "menu");
			expect(trigger).toBeDisabled();
		});
		expect(createFlowRun).toHaveBeenCalledTimes(1);

		resolveRequest?.();
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);
	});

	it("resets run controls when the selected deployment changes", async () => {
		const flow = createFakeFlow();
		const deployments = [
			createFakeDeployment({ flow_id: flow.id, name: "dep-one" }),
			createFakeDeployment({ flow_id: flow.id, name: "dep-two" }),
		];
		mockCount(flow.id, 2);
		mockPaginate({ results: deployments, count: 2 }, []);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await user.click(
			await screen.findByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("option", { name: "dep-one" }));
		expect(
			screen.getByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent("dep-one");

		await user.click(
			screen.getByRole("button", { name: "Select a deployment" }),
		);
		await user.click(await screen.findByRole("option", { name: "dep-two" }));
		expect(
			screen.getByRole("button", { name: "Select a deployment" }),
		).toHaveTextContent("dep-two");
	});

	it("opens the parameters dialog for required parameters and closes both on success", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({
			flow_id: flow.id,
			enforce_parameter_schema: true,
			parameters: { project: "default-project" },
			parameter_openapi_schema: {
				title: "Parameters",
				type: "object",
				properties: {
					project: { title: "Project", type: "string" },
				},
				required: ["project"],
			},
		});
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Select a deployment" }),
			).toHaveTextContent(deployment.name),
		);
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);

		// Parameters dialog opens for the required-parameters deployment
		const paramsDialog = await screen.findByRole("dialog", {
			name: "Run Deployment",
		});
		await user.click(
			await within(paramsDialog).findByRole("button", { name: "Run" }),
		);

		await waitFor(() => expect(createFlowRun).toHaveBeenCalledTimes(1));
		await waitFor(() =>
			expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
		);
	});

	it("keeps the parameters dialog open when its submission fails", async () => {
		const flow = createFakeFlow();
		const deployment = createFakeDeployment({
			flow_id: flow.id,
			enforce_parameter_schema: true,
			parameters: { project: "default-project" },
			parameter_openapi_schema: {
				title: "Parameters",
				type: "object",
				properties: {
					project: { title: "Project", type: "string" },
				},
				required: ["project"],
			},
		});
		mockCount(flow.id, 1);
		mockPaginate({ results: [deployment], count: 1 }, []);
		server.use(
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () =>
				HttpResponse.error(),
			),
		);
		await renderAction(<FlowRunAction flow={flow} />);
		const user = await openDialog();

		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "Select a deployment" }),
			).toHaveTextContent(deployment.name),
		);
		await user.click(screen.getByRole("button", { name: "Run" }));
		await user.click(
			await screen.findByRole("menuitem", { name: "Quick run" }),
		);

		const paramsDialog = await screen.findByRole("dialog", {
			name: "Run Deployment",
		});
		await user.click(
			await within(paramsDialog).findByRole("button", { name: "Run" }),
		);

		await waitFor(() =>
			expect(
				screen.getByRole("dialog", { name: "Run Deployment" }),
			).toBeVisible(),
		);
	});
});
