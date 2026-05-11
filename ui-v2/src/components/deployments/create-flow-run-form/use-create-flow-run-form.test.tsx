import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { type ReactNode, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { useCreateFlowRunForm } from "./use-create-flow-run-form";

vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual<typeof import("@tanstack/react-router")>(
		"@tanstack/react-router",
	);
	return {
		...actual,
		useNavigate: () => vi.fn(),
		Link: ({ children }: { children: ReactNode }) => <>{children}</>,
	};
});

const buildWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});
	const Wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("useCreateFlowRunForm", () => {
	it("initializes parameter values from the deployment", () => {
		const deployment = createFakeDeployment({
			parameters: { foo: "bar", count: 1 },
		});

		const { result } = renderHook(
			() => useCreateFlowRunForm(deployment, undefined),
			{ wrapper: buildWrapper() },
		);

		expect(result.current.parametersFormValues).toEqual({
			foo: "bar",
			count: 1,
		});
	});

	it("prefers `overrideParameters` over the deployment's parameters", () => {
		const deployment = createFakeDeployment({
			parameters: { foo: "bar" },
		});

		const { result } = renderHook(
			() => useCreateFlowRunForm(deployment, { foo: "override" }),
			{ wrapper: buildWrapper() },
		);

		expect(result.current.parametersFormValues).toEqual({ foo: "override" });
	});

	it("preserves user edits when the deployment object reference changes (refetch)", () => {
		// Simulates the failure described in OSS-7952: the deployment query
		// refetches on a 30s interval and on window focus, returning a new
		// object reference. The form should not overwrite in-flight edits.
		const initialDeployment = createFakeDeployment({
			parameters: { foo: "bar" },
		});

		const { result, rerender } = renderHook(
			({ deployment }: { deployment: Deployment }) =>
				useCreateFlowRunForm(deployment, undefined),
			{
				wrapper: buildWrapper(),
				initialProps: { deployment: initialDeployment },
			},
		);

		act(() => {
			result.current.setParametersFormValues({ foo: "edited" });
		});
		expect(result.current.parametersFormValues).toEqual({ foo: "edited" });

		const refetchedDeployment: Deployment = {
			...initialDeployment,
			parameters: { foo: "bar" },
		};
		rerender({ deployment: refetchedDeployment });

		expect(result.current.parametersFormValues).toEqual({ foo: "edited" });
	});

	it("preserves user edits to react-hook-form fields across deployment refetches", () => {
		const initialDeployment = createFakeDeployment({
			tags: ["initial"],
			enforce_parameter_schema: true,
		});

		const { result, rerender } = renderHook(
			({ deployment }: { deployment: Deployment }) =>
				useCreateFlowRunForm(deployment, undefined),
			{
				wrapper: buildWrapper(),
				initialProps: { deployment: initialDeployment },
			},
		);

		act(() => {
			result.current.form.setValue("name", "my-run-name");
			result.current.form.setValue("tags", ["edited-tag"]);
			result.current.form.setValue("enforce_parameter_schema", false);
		});

		const refetchedDeployment: Deployment = {
			...initialDeployment,
			// Simulate a benign update to a field unrelated to the form.
			updated: new Date().toISOString(),
		};
		rerender({ deployment: refetchedDeployment });

		expect(result.current.form.getValues("name")).toBe("my-run-name");
		expect(result.current.form.getValues("tags")).toEqual(["edited-tag"]);
		expect(result.current.form.getValues("enforce_parameter_schema")).toBe(
			false,
		);
	});

	it("does not re-initialize when `overrideParameters` reference changes", () => {
		// If a parent passes a fresh object identity on each render (a common
		// React mistake), the hook should still not clobber user edits.
		const deployment = createFakeDeployment({ parameters: {} });

		const { result, rerender } = renderHook(
			() => {
				const [override] = useState<Record<string, unknown>>({ foo: "x" });
				return useCreateFlowRunForm(deployment, override);
			},
			{ wrapper: buildWrapper() },
		);

		act(() => {
			result.current.setParametersFormValues({ foo: "y" });
		});
		expect(result.current.parametersFormValues).toEqual({ foo: "y" });

		rerender();
		expect(result.current.parametersFormValues).toEqual({ foo: "y" });
	});
});
