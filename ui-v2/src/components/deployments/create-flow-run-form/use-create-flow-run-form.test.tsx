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
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment, createFakeFlowRun } from "@/mocks";
import {
	type AdditionalOptionsOverrides,
	useCreateFlowRunForm,
} from "./use-create-flow-run-form";

type HookResult = ReturnType<typeof useCreateFlowRunForm>;

const renderUseCreateFlowRunForm = async (
	initialDeployment: Deployment,
	initialOverride: Record<string, unknown> | undefined = undefined,
	initialAdditionalOptionsOverrides:
		| AdditionalOptionsOverrides
		| undefined = undefined,
) => {
	const resultRef: { current: HookResult | null } = { current: null };
	let setDeploymentState: (deployment: Deployment) => void = () => {};
	let setOverrideState: (
		override: Record<string, unknown> | undefined,
	) => void = () => {};

	const HookHarness = () => {
		const [deployment, setDeployment] = useState(initialDeployment);
		const [override, setOverride] = useState<
			Record<string, unknown> | undefined
		>(initialOverride);
		setDeploymentState = setDeployment;
		setOverrideState = setOverride;
		resultRef.current = useCreateFlowRunForm(
			deployment,
			override,
			initialAdditionalOptionsOverrides,
		);
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

	const result = {
		get current(): HookResult {
			if (!resultRef.current) {
				throw new Error("hook result not yet available");
			}
			return resultRef.current;
		},
	};

	return {
		result,
		setDeployment: (deployment: Deployment) =>
			act(() => setDeploymentState(deployment)),
		setOverrideParameters: (override: Record<string, unknown> | undefined) =>
			act(() => setOverrideState(override)),
	};
};

describe("useCreateFlowRunForm", () => {
	it("initializes parameter values from the deployment", async () => {
		const deployment = createFakeDeployment({
			parameters: { foo: "bar", count: 1 },
		});

		const { result } = await renderUseCreateFlowRunForm(deployment);

		expect(result.current.parametersFormValues).toEqual({
			foo: "bar",
			count: 1,
		});
	});

	it("prefers `overrideParameters` over the deployment's parameters", async () => {
		const deployment = createFakeDeployment({
			parameters: { foo: "bar" },
		});

		const { result } = await renderUseCreateFlowRunForm(deployment, {
			foo: "override",
		});

		expect(result.current.parametersFormValues).toEqual({ foo: "override" });
	});

	it("preserves user edits when the deployment object reference changes (refetch)", async () => {
		// Simulates the failure described in OSS-7952: the deployment query
		// refetches on a 30s interval and on window focus, returning a new
		// object reference. The form should not overwrite in-flight edits.
		const initialDeployment = createFakeDeployment({
			parameters: { foo: "bar" },
		});

		const { result, setDeployment } =
			await renderUseCreateFlowRunForm(initialDeployment);

		act(() => {
			result.current.setParametersFormValues({ foo: "edited" });
		});
		expect(result.current.parametersFormValues).toEqual({ foo: "edited" });

		setDeployment({
			...initialDeployment,
			parameters: { foo: "bar" },
		});

		expect(result.current.parametersFormValues).toEqual({ foo: "edited" });
	});

	it("preserves user edits to react-hook-form fields across deployment refetches", async () => {
		const initialDeployment = createFakeDeployment({
			tags: ["initial"],
			enforce_parameter_schema: true,
		});

		const { result, setDeployment } =
			await renderUseCreateFlowRunForm(initialDeployment);

		act(() => {
			result.current.form.setValue("name", "my-run-name");
			result.current.form.setValue("tags", ["edited-tag"]);
			result.current.form.setValue("enforce_parameter_schema", false);
		});

		setDeployment({
			...initialDeployment,
			// Simulate a benign update to a field unrelated to the form.
			updated: new Date().toISOString(),
		});

		expect(result.current.form.getValues("name")).toBe("my-run-name");
		expect(result.current.form.getValues("tags")).toEqual(["edited-tag"]);
		expect(result.current.form.getValues("enforce_parameter_schema")).toBe(
			false,
		);
	});

	it("does not re-initialize when `overrideParameters` reference changes", async () => {
		// If a parent passes a fresh object identity on each render (a common
		// React mistake), the hook should still not clobber user edits.
		const deployment = createFakeDeployment({ parameters: {} });

		const { result, setOverrideParameters } = await renderUseCreateFlowRunForm(
			deployment,
			{ foo: "x" },
		);

		act(() => {
			result.current.setParametersFormValues({ foo: "y" });
		});
		expect(result.current.parametersFormValues).toEqual({ foo: "y" });

		setOverrideParameters({ foo: "x" });
		expect(result.current.parametersFormValues).toEqual({ foo: "y" });
	});

	it("initializes additional options from overrideAdditionalOptions", async () => {
		const deployment = createFakeDeployment({
			tags: ["deployment-tag"],
			work_queue_name: "default-queue",
			job_variables: { default: "var" },
		});

		const { result } = await renderUseCreateFlowRunForm(deployment, undefined, {
			message: "copied message",
			tags: ["copied-tag"],
			work_queue_name: "copied-queue",
			retries: 3,
			retry_delay: 5,
			job_variables: { image: "my-ecr-uri" },
		});

		expect(result.current.form.getValues("state.message")).toBe(
			"copied message",
		);
		expect(result.current.form.getValues("tags")).toEqual(["copied-tag"]);
		expect(result.current.form.getValues("work_queue_name")).toBe(
			"copied-queue",
		);
		expect(result.current.form.getValues("empirical_policy.retries")).toBe(3);
		expect(result.current.form.getValues("empirical_policy.retry_delay")).toBe(
			5,
		);
		expect(result.current.form.getValues("job_variables")).toBe(
			'{"image":"my-ecr-uri"}',
		);
	});

	it("includes copied tags in the create flow run payload", async () => {
		const deployment = createFakeDeployment({ parameters: {} });
		let requestBody: Record<string, unknown> = {};
		server.use(
			http.post(
				buildApiUrl("/deployments/:id/create_flow_run"),
				async ({ request }) => {
					requestBody = (await request.json()) as Record<string, unknown>;
					return HttpResponse.json(createFakeFlowRun({ id: "new-run-id" }));
				},
			),
		);

		const { result } = await renderUseCreateFlowRunForm(deployment, undefined, {
			tags: ["copied-tag"],
		});

		await act(async () => {
			await result.current.form.handleSubmit(result.current.onCreate)();
		});

		await waitFor(() => {
			expect(requestBody.tags).toEqual(["copied-tag"]);
		});
	});
});
