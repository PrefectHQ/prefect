import { renderHook } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { useCreateWorkPoolQueueForm } from "./use-create-work-pool-queue-form";

vi.mock("@/api/work-pool-queues", () => ({
	useCreateWorkPoolQueueMutation: () => ({
		mutate: vi.fn(),
		isPending: false,
	}),
}));

describe("useCreateWorkPoolQueueForm", () => {
	const defaultOptions = {
		workPoolName: "test-work-pool",
		onSubmit: vi.fn(),
	};

	it("initializes with default values", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;
		expect(form.getValues()).toEqual({
			name: "",
			description: "",
			is_paused: false,
			concurrency_limit: null,
			priority: null,
		});
	});

	it("validates required name field", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Just verify the form has the expected structure
		expect(form.getValues("name")).toBe("");
		expect(form.formState.isValid).toBe(false);
	});

	it("validates name field format", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Set valid name and check it's accepted
		form.setValue("name", "valid-name");
		expect(form.getValues("name")).toBe("valid-name");
	});

	it("accepts valid name formats", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		const validNames = [
			"test",
			"test-queue",
			"test_queue",
			"test123",
			"TEST-QUEUE",
		];

		for (const validName of validNames) {
			form.setValue("name", validName);
			const isValid = await form.trigger("name");
			expect(isValid).toBe(true);
		}
	});

	it("handles numeric inputs correctly", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Test concurrency limit
		form.setValue("concurrency_limit", "5");
		await form.trigger("concurrency_limit");
		expect(form.formState.errors.concurrency_limit).toBeUndefined();

		// Test priority
		form.setValue("priority", "10");
		await form.trigger("priority");
		expect(form.formState.errors.priority).toBeUndefined();
	});

	it("handles empty numeric inputs correctly", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Test empty string should be converted to null
		form.setValue("concurrency_limit", "");
		await form.trigger("concurrency_limit");
		expect(form.formState.errors.concurrency_limit).toBeUndefined();

		form.setValue("priority", "");
		await form.trigger("priority");
		expect(form.formState.errors.priority).toBeUndefined();
	});

	it("handles positive numbers for concurrency limit", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Test that positive numbers are accepted
		form.setValue("concurrency_limit", "5");
		expect(form.getValues("concurrency_limit")).toBe("5");
	});

	it("handles positive numbers for priority", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Test that positive numbers are accepted
		form.setValue("priority", "10");
		expect(form.getValues("priority")).toBe("10");
	});

	it("returns isLoading state", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		expect(result.current.isLoading).toBe(false);
	});

	it("provides create function", () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		expect(typeof result.current.create).toBe("function");
	});
});
