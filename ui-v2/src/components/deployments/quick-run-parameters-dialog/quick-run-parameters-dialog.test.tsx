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
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeDeployment, createFakeFlowRun } from "@/mocks";
import { QuickRunParametersDialog } from "./quick-run-parameters-dialog";

const parameterSchema = {
	title: "Parameters",
	type: "object",
	properties: {
		project: {
			title: "Project",
			type: "string",
		},
	},
	required: ["project"],
};

const createTestRouter = (children: ReactNode) => {
	const rootRoute = createRootRoute({
		component: () => (
			<>
				<Toaster />
				{children}
			</>
		),
	});

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});
};

describe("QuickRunParametersDialog", () => {
	it("renders the deployment parameter form", async () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: parameterSchema,
		});

		render(
			<QuickRunParametersDialog
				deployment={deployment}
				open
				onOpenChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Run Deployment" }),
		).toBeInTheDocument();
		expect(await screen.findByText("Project")).toBeInTheDocument();
		expect(screen.getByText("Validate parameters")).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
	});

	it("validates parameters and creates a flow run", async () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: parameterSchema,
			enforce_parameter_schema: true,
		});
		const flowRun = createFakeFlowRun();
		const createFlowRun = vi.fn<(body: Record<string, unknown>) => void>();
		server.use(
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({ valid: true, errors: [] }),
			),
			http.post(
				buildApiUrl("/deployments/:id/create_flow_run"),
				async ({ request }) => {
					const body = (await request.json()) as Record<string, unknown>;
					createFlowRun(body);
					return HttpResponse.json(flowRun);
				},
			),
		);
		const user = userEvent.setup();
		const router = createTestRouter(
			<QuickRunParametersDialog
				deployment={deployment}
				open
				onOpenChange={vi.fn()}
			/>,
		);

		await waitFor(() =>
			render(<RouterProvider router={router} />, { wrapper: createWrapper() }),
		);
		await user.type(
			await screen.findByRole("textbox", { name: "Project" }),
			"prefect",
		);
		await user.click(screen.getByRole("button", { name: "Run" }));

		await waitFor(() => expect(createFlowRun).toHaveBeenCalledOnce());
		expect(createFlowRun).toHaveBeenCalledWith(
			expect.objectContaining({
				parameters: { project: "prefect" },
				enforce_parameter_schema: true,
			}),
		);
		const requestBody = createFlowRun.mock.calls[0]?.[0];
		expect(requestBody?.state).toEqual(
			expect.objectContaining({
				message: "Run from the Prefect UI",
			}),
		);
		await waitFor(() =>
			expect(screen.getByRole("button", { name: /view run/i })).toBeVisible(),
		);
	});

	it("does not create a flow run when parameter validation fails", async () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: parameterSchema,
			enforce_parameter_schema: true,
		});
		const createFlowRun = vi.fn();
		server.use(
			http.post(buildApiUrl("/ui/schemas/validate"), () =>
				HttpResponse.json({
					valid: false,
					errors: [
						{
							type: "value_error",
							property: "project",
							errors: ["Project is required"],
						},
					],
				}),
			),
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		const user = userEvent.setup();
		render(
			<QuickRunParametersDialog
				deployment={deployment}
				open
				onOpenChange={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Run" }));

		await waitFor(() =>
			expect(screen.getByText("Project is required")).toBeVisible(),
		);
		expect(createFlowRun).not.toHaveBeenCalled();
	});

	it("surfaces parameter validation errors and does not create a flow run", async () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: parameterSchema,
			enforce_parameter_schema: true,
		});
		const createFlowRun = vi.fn();
		server.use(
			http.post(
				buildApiUrl("/ui/schemas/validate"),
				() => new HttpResponse(null, { status: 500 }),
			),
			http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
				createFlowRun();
				return HttpResponse.json(createFakeFlowRun());
			}),
		);
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<QuickRunParametersDialog
					deployment={deployment}
					open
					onOpenChange={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Run" }));

		await waitFor(() =>
			expect(
				screen.getByText("Server error occurred validating schema"),
			).toBeVisible(),
		);
		expect(createFlowRun).not.toHaveBeenCalled();
	});
});
