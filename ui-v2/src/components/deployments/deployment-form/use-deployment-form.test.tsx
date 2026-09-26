import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { act, render, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { useDeploymentForm } from "./use-deployment-form";

type HookResult = ReturnType<typeof useDeploymentForm>;

const renderUseDeploymentForm = async (
	deployment: Deployment,
	mode: "edit" | "duplicate",
) => {
	const resultRef: { current: HookResult | null } = { current: null };

	const HookHarness = () => {
		resultRef.current = useDeploymentForm(deployment, { mode });
		return null;
	};

	const rootRoute = createRootRoute({ component: HookHarness });
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	render(<RouterProvider router={router} />, { wrapper: createWrapper() });
	await waitFor(() => {
		expect(resultRef.current).not.toBeNull();
	});

	return {
		get current(): HookResult {
			if (!resultRef.current) {
				throw new Error("hook result not yet available");
			}
			return resultRef.current;
		},
	};
};

describe("useDeploymentForm", () => {
	it("initializes job_variables as a JSON string from the deployment", async () => {
		const deployment = createFakeDeployment({
			job_variables: { env: { FOO: "bar" } },
		});

		const result = await renderUseDeploymentForm(deployment, "edit");

		await waitFor(() => {
			expect(result.current.form.getValues("job_variables")).toBe(
				'{"env":{"FOO":"bar"}}',
			);
		});
	});

	it("sends an empty object when job_variables is cleared on edit", async () => {
		const deployment = createFakeDeployment({
			job_variables: { env: { FOO: "bar" } },
		});
		let requestBody: Record<string, unknown> = {};
		server.use(
			http.patch(buildApiUrl("/deployments/:id"), async ({ request }) => {
				requestBody = (await request.json()) as Record<string, unknown>;
				return new HttpResponse(null, { status: 204 });
			}),
		);

		const result = await renderUseDeploymentForm(deployment, "edit");
		await waitFor(() => {
			expect(result.current.form.getValues("name")).toBe(deployment.name);
		});

		act(() => {
			result.current.form.setValue("job_variables", "");
		});
		await act(async () => {
			await result.current.form.handleSubmit(result.current.onSave)();
		});

		await waitFor(() => {
			expect(requestBody.job_variables).toEqual({});
		});
	});

	it("sends an empty object when job_variables is blank on duplicate", async () => {
		const deployment = createFakeDeployment({ job_variables: {} });
		let requestBody: Record<string, unknown> = {};
		server.use(
			http.post(buildApiUrl("/deployments/"), async ({ request }) => {
				requestBody = (await request.json()) as Record<string, unknown>;
				return HttpResponse.json(createFakeDeployment(), { status: 201 });
			}),
		);

		const result = await renderUseDeploymentForm(deployment, "duplicate");
		await waitFor(() => {
			expect(result.current.form.getValues("name")).toBe(deployment.name);
		});

		act(() => {
			result.current.form.setValue("name", `${deployment.name}-copy`);
		});
		await act(async () => {
			await result.current.form.handleSubmit(result.current.onSave)();
		});

		await waitFor(() => {
			expect(requestBody.job_variables).toEqual({});
		});
	});
});
