import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useWorkPoolValidation } from "./use-work-pool-validation";

describe("useWorkPoolValidation", () => {
	describe("validateInfrastructureType", () => {
		it("returns valid when type is provided", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInfrastructureType({
				type: "process",
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("returns invalid when type is missing", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInfrastructureType({});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.type).toContain(
				"Infrastructure type is required",
			);
		});
	});

	describe("validateInformation", () => {
		it("returns valid for correct work pool information", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "my-work-pool",
				description: "Test description",
				concurrencyLimit: 10,
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("returns invalid when name is missing", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				description: "Test description",
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.name).toContain("Name is required");
		});

		it("returns invalid for invalid name format", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "my work pool!",
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.name).toContain(
				"Name can only contain letters, numbers, hyphens, and underscores",
			);
		});

		it("returns invalid for names starting with 'prefect'", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "prefect-pool",
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.name).toContain(
				'Work pools starting with "prefect" are reserved for internal use.',
			);
		});

		it("returns invalid for names starting with 'Prefect' (case insensitive)", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "Prefect-Pool",
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.name).toContain(
				'Work pools starting with "prefect" are reserved for internal use.',
			);
		});

		it("accepts null concurrency limit", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "my-work-pool",
				concurrencyLimit: null,
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("accepts 0 as concurrency limit", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "my-work-pool",
				concurrencyLimit: 0,
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("returns invalid for negative concurrency limit", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateInformation({
				name: "my-work-pool",
				concurrencyLimit: -1,
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.concurrencyLimit).toBeDefined();
		});
	});

	describe("validateConfiguration", () => {
		it("returns valid for any base job template", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateConfiguration({
				baseJobTemplate: {
					job_configuration: { key: "value" },
					variables: {},
				},
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("returns valid when base job template is undefined", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateConfiguration({});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});
	});

	describe("validateAll", () => {
		it("validates all fields together", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateAll({
				type: "process",
				name: "my-work-pool",
				description: "Test",
				concurrencyLimit: 10,
				isPaused: false,
				baseJobTemplate: { job_configuration: {} },
			});

			expect(validation.isValid).toBe(true);
			expect(validation.errors).toEqual({});
		});

		it("returns all validation errors", () => {
			const { result } = renderHook(() => useWorkPoolValidation());
			const validation = result.current.validateAll({
				name: "prefect-invalid!",
			});

			expect(validation.isValid).toBe(false);
			expect(validation.errors.type).toBeDefined();
			expect(validation.errors.name).toBeDefined();
		});
	});
});
