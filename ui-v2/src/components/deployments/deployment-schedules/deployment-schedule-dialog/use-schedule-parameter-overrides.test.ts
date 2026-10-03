import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { DeploymentSchedule } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { useScheduleParameterOverrides } from "./use-schedule-parameter-overrides";

const PARAMETER_SCHEMA = {
	type: "object",
	title: "Parameters",
	properties: {
		name: { type: "string", title: "name", position: 0 },
	},
	required: ["name"],
};

const MOCK_SCHEDULE: DeploymentSchedule = {
	active: true,
	created: "0",
	deployment_id: "deployment-id",
	id: "schedule-id",
	updated: "0",
	schedule: { cron: "* * * * *", day_or: true, timezone: "UTC" },
	parameters: { name: "override" },
};

const mockValidation = (
	response: { valid: boolean; errors: unknown[] } | "error",
) => {
	server.use(
		http.post(buildApiUrl("/ui/schemas/validate"), () =>
			response === "error"
				? new HttpResponse(null, { status: 500 })
				: HttpResponse.json(response),
		),
	);
};

describe("useScheduleParameterOverrides", () => {
	it("relaxes the deployment schema so overrides are partial", () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment),
		);

		expect(result.current.schema?.required).toEqual([]);
		expect(result.current.schema?.properties).toEqual(
			PARAMETER_SCHEMA.properties,
		);
	});

	it("has no schema when the deployment schema is not an object schema", () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: { type: "string" },
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment),
		);

		expect(result.current.schema).toBeUndefined();
	});

	it("initializes values from the schedule being edited", () => {
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
			parameters: { name: "deployment default" },
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment, MOCK_SCHEDULE),
		);

		expect(result.current.values).toEqual({ name: "override" });
	});

	it("skips validation when the deployment does not enforce its schema", async () => {
		mockValidation("error");
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
			enforce_parameter_schema: false,
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment),
		);

		await expect(result.current.validate()).resolves.toBe(true);
		expect(result.current.errors).toEqual([]);
	});

	it("surfaces validation errors and clears them once valid", async () => {
		const errors = [{ index: 0, property: "name", errors: ["not a string"] }];
		mockValidation({ valid: false, errors });
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
			enforce_parameter_schema: true,
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment),
		);

		await act(async () => {
			await expect(result.current.validate()).resolves.toBe(false);
		});
		await waitFor(() => expect(result.current.errors).toEqual(errors));

		mockValidation({ valid: true, errors: [] });

		await act(async () => {
			await expect(result.current.validate()).resolves.toBe(true);
		});
		await waitFor(() => expect(result.current.errors).toEqual([]));
	});

	it("validates the deployment parameters merged with the overrides", async () => {
		let body: unknown;
		server.use(
			http.post(buildApiUrl("/ui/schemas/validate"), async ({ request }) => {
				body = await request.json();
				return HttpResponse.json({ valid: true, errors: [] });
			}),
		);
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
			parameters: { name: "deployment default", other: "kept" },
			enforce_parameter_schema: true,
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment, MOCK_SCHEDULE),
		);

		await expect(result.current.validate()).resolves.toBe(true);
		expect(body).toEqual({
			schema: PARAMETER_SCHEMA,
			values: { name: "override", other: "kept" },
		});
	});

	it("fails validation when the request errors", async () => {
		mockValidation("error");
		const deployment = createFakeDeployment({
			parameter_openapi_schema: PARAMETER_SCHEMA,
			enforce_parameter_schema: true,
		});

		const { result } = renderHook(() =>
			useScheduleParameterOverrides(deployment),
		);

		await expect(result.current.validate()).resolves.toBe(false);
	});
});
