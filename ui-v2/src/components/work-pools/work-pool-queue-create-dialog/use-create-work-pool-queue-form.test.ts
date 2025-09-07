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

	it("validates required name field", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Trigger validation
		const isValid = await form.trigger("name");

		expect(isValid).toBe(false);
		expect(form.formState.errors.name?.message).toBe("Name is required");
	});

	it("validates name field format", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		// Set invalid name
		form.setValue("name", "invalid name with spaces");
		const isValid = await form.trigger("name");

		expect(isValid).toBe(false);
		expect(form.formState.errors.name?.message).toBe(
			"Name can only contain letters, numbers, hyphens, and underscores",
		);
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

	it("validates positive numbers for concurrency limit", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		form.setValue("concurrency_limit", "-1");
		const isValid = await form.trigger("concurrency_limit");

		expect(isValid).toBe(false);
		expect(form.formState.errors.concurrency_limit?.message).toBe(
			"Concurrency limit must be greater than 0",
		);
	});

	it("validates positive numbers for priority", async () => {
		const { result } = renderHook(
			() => useCreateWorkPoolQueueForm(defaultOptions),
			{
				wrapper: createWrapper(),
			},
		);

		const { form } = result.current;

		form.setValue("priority", "-1");
		const isValid = await form.trigger("priority");

		expect(isValid).toBe(false);
		expect(form.formState.errors.priority?.message).toBe(
			"Priority must be greater than 0",
		);
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
