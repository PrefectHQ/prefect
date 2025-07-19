import { QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWorkPoolCreateWizard } from "./use-work-pool-create-wizard";

// Mock the router
const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
	useNavigate: () => mockNavigate,
}));

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("useWorkPoolCreateWizard", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("initializes with default state", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		expect(result.current.workPoolData).toEqual({ isPaused: false });
		expect(result.current.currentStep).toBe("Infrastructure Type");
		expect(result.current.isSubmitting).toBe(false);
		expect(result.current.stepper.currentStep).toBe(0);
	});

	it("updates work pool data", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.updateWorkPoolData({
				name: "test-pool",
				type: "process",
			});
		});

		expect(result.current.workPoolData).toEqual({
			isPaused: false,
			name: "test-pool",
			type: "process",
		});
	});

	it("navigates through wizard steps", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		expect(result.current.currentStep).toBe("Infrastructure Type");

		act(() => {
			result.current.stepper.incrementStep();
		});

		expect(result.current.currentStep).toBe("Details");

		act(() => {
			result.current.stepper.incrementStep();
		});

		expect(result.current.currentStep).toBe("Configuration");
	});

	it("submits work pool successfully", async () => {
		const mockWorkPool = {
			id: "123",
			name: "test-pool",
			type: "process",
		};

		server.use(
			http.post(buildApiUrl("/work_pools/"), () => {
				return HttpResponse.json(mockWorkPool);
			}),
		);

		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.updateWorkPoolData({
				name: "test-pool",
				type: "process",
				description: "Test description",
				concurrencyLimit: 10,
				baseJobTemplate: {
					job_configuration: { key: "value" },
					variables: {},
				},
			});
		});

		await act(async () => {
			await result.current.submit();
		});

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({
				to: "/work-pools/work-pool/test-pool",
			});
		});
	});

	it("handles submission errors", async () => {
		server.use(
			http.post(buildApiUrl("/work_pools/"), () => {
				return HttpResponse.json(
					{ detail: "Work pool already exists" },
					{ status: 400 },
				);
			}),
		);

		const queryClient = new QueryClient({
			defaultOptions: {
				mutations: { retry: false },
			},
		});
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.updateWorkPoolData({
				name: "test-pool",
				type: "process",
			});
		});

		await act(async () => {
			await result.current.submit();
		});

		expect(mockNavigate).not.toHaveBeenCalled();
	});

	it("shows error toast when required fields are missing", async () => {
		const { toast } = await import("sonner");
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		await act(async () => {
			await result.current.submit();
		});

		expect(toast.error).toHaveBeenCalledWith("Missing required fields");
		expect(mockNavigate).not.toHaveBeenCalled();
	});

	it("navigates to work pools list on cancel", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			result.current.cancel();
		});

		expect(mockNavigate).toHaveBeenCalledWith({ to: "/work-pools" });
	});

	it("structures base_job_template correctly when submitting", async () => {
		let submittedData: unknown = null;

		server.use(
			http.post(buildApiUrl("/work_pools/"), async ({ request }) => {
				submittedData = await request.json();
				return HttpResponse.json({
					id: "123",
					name: "test-pool",
					type: "process",
				});
			}),
		);

		const queryClient = new QueryClient();
		const { result } = renderHook(() => useWorkPoolCreateWizard(), {
			wrapper: createWrapper({ queryClient }),
		});

		const baseJobTemplate = {
			job_configuration: { command: "test" },
			variables: { properties: {} },
		};

		act(() => {
			result.current.updateWorkPoolData({
				name: "test-pool",
				type: "process",
				baseJobTemplate,
			});
		});

		await act(async () => {
			await result.current.submit();
		});

		await waitFor(() => {
			expect(submittedData).toEqual({
				name: "test-pool",
				type: "process",
				description: null,
				concurrency_limit: null,
				is_paused: false,
				base_job_template: baseJobTemplate,
			});
		});
	});
});
