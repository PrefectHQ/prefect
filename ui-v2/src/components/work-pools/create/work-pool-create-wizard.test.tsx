import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

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

const mockWorkersResponse = {
	prefect: {
		process: {
			type: "process",
			display_name: "Process",
			description: "Execute flow runs as subprocesses",
			logo_url: "https://example.com/process.png",
			is_beta: false,
			default_base_job_configuration: {
				job_configuration: { command: "{{ command }}" },
				variables: {
					properties: {
						command: { type: "string", default: "echo 'Hello'" },
					},
				},
			},
		},
	},
};

// Wrapper component with Suspense
const WorkPoolCreateWizardWithSuspense = () => (
	<Suspense fallback={<div>Loading...</div>}>
		<WorkPoolCreateWizard />
	</Suspense>
);

describe("WorkPoolCreateWizard", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		server.use(
			http.get(
				buildApiUrl("/collections/views/aggregate-worker-metadata"),
				() => {
					return HttpResponse.json(mockWorkersResponse);
				},
			),
		);
	});

	it("renders the wizard with stepper", async () => {
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Wait for stepper to render
		await waitFor(() => {
			expect(screen.getByText("Infrastructure Type")).toBeInTheDocument();
		});
		expect(screen.getByText("Details")).toBeInTheDocument();
		expect(screen.getByText("Configuration")).toBeInTheDocument();

		// Check first step is active
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});
	});

	it("navigates through wizard steps", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Wait for infrastructure types to load
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		// Select infrastructure type by clicking the radio button
		const processRadio = screen.getByRole("radio", { name: /process/i });
		await user.click(processRadio);

		// Should auto-advance to Details step
		await waitFor(() => {
			expect(screen.getByLabelText("Name")).toBeInTheDocument();
		});

		// Fill in details
		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "test-pool");

		// Click next to go to Configuration step
		const nextButton = screen.getByText("Next");
		await user.click(nextButton);

		// Should be on Configuration step
		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Defaults" })).toBeInTheDocument();
		});
	});

	it("validates required fields before advancing", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Wait for infrastructure types to load
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		// Try to go to next step without selecting type
		const nextButton = screen.getByText("Next");
		await user.click(nextButton);

		// Should still be on first step
		expect(screen.getByText("Process")).toBeInTheDocument();
	});

	it("allows navigation back through steps", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Go through steps
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processRadio = screen.getByRole("radio", { name: /process/i });
		await user.click(processRadio);

		// Should auto-advance to Details step
		await waitFor(() => {
			expect(screen.getByLabelText("Name")).toBeInTheDocument();
		});

		// Click back
		const backButton = screen.getByText("Previous");
		await user.click(backButton);

		// Should be back on infrastructure type step
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});
	});

	it("submits work pool successfully", async () => {
		const { toast } = await import("sonner");
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		server.use(
			http.post(buildApiUrl("/work_pools/"), () => {
				return HttpResponse.json({
					id: "123",
					name: "test-pool",
					type: "process",
				});
			}),
		);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Select infrastructure type
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processRadio = screen.getByRole("radio", { name: /process/i });
		await user.click(processRadio);

		// Fill in details
		await waitFor(() => {
			expect(screen.getByLabelText("Name")).toBeInTheDocument();
		});

		const nameInput = screen.getByLabelText("Name");
		await user.type(nameInput, "test-pool");

		// Go to configuration
		const nextButton = screen.getByText("Next");
		await user.click(nextButton);

		// Submit
		await waitFor(() => {
			expect(
				screen.getByRole("button", { name: "Create" }),
			).toBeInTheDocument();
		});

		const createButton = screen.getByRole("button", { name: "Create" });
		await user.click(createButton);

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith(
				"Work pool created successfully",
			);
			expect(mockNavigate).toHaveBeenCalledWith({
				to: "/work-pools/work-pool/test-pool",
			});
		});
	});

	it("handles submission errors", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient({
			defaultOptions: {
				mutations: { retry: false },
			},
		});
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		server.use(
			http.post(buildApiUrl("/work_pools/"), () => {
				return HttpResponse.json(
					{ detail: "Work pool already exists" },
					{ status: 400 },
				);
			}),
		);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Go through wizard quickly
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processRadio = screen.getByRole("radio", { name: /process/i });
		await user.click(processRadio);

		await waitFor(() => {
			expect(screen.getByLabelText("Name")).toBeInTheDocument();
		});

		await user.type(screen.getByLabelText("Name"), "test-pool");
		await user.click(screen.getByText("Next"));

		await waitFor(() => {
			expect(
				screen.getByRole("button", { name: "Create" }),
			).toBeInTheDocument();
		});

		await user.click(screen.getByRole("button", { name: "Create" }));

		// Should not navigate on error
		await waitFor(() => {
			expect(mockNavigate).not.toHaveBeenCalled();
		});
	});

	it("cancels and navigates to work pools list", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Wait for the component to load
		await waitFor(() => {
			expect(screen.getByText("Cancel")).toBeInTheDocument();
		});

		const cancelButton = screen.getByText("Cancel");
		await user.click(cancelButton);

		expect(mockNavigate).toHaveBeenCalledWith({ to: "/work-pools" });
	});

	it("disables submit button when submitting", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		// Prefill the cache with workers data
		queryClient.setQueryData(["workers", "list"], mockWorkersResponse);

		let resolveSubmit: (() => void) | undefined;
		const submitPromise = new Promise<void>((resolve) => {
			resolveSubmit = resolve;
		});

		server.use(
			http.post(buildApiUrl("/work_pools/"), async () => {
				await submitPromise;
				return HttpResponse.json({
					id: "123",
					name: "test-pool",
					type: "process",
				});
			}),
		);

		render(<WorkPoolCreateWizardWithSuspense />, {
			wrapper: createWrapper({ queryClient }),
		});

		// Go through wizard
		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processRadio = screen.getByRole("radio", { name: /process/i });
		await user.click(processRadio);

		await waitFor(() => {
			expect(screen.getByLabelText("Name")).toBeInTheDocument();
		});

		await user.type(screen.getByLabelText("Name"), "test-pool");
		await user.click(screen.getByText("Next"));

		await waitFor(() => {
			expect(
				screen.getByRole("button", { name: "Create" }),
			).toBeInTheDocument();
		});

		const createButton = screen.getByRole("button", { name: "Create" });
		await user.click(createButton);

		// Button should be disabled while submitting
		expect(createButton).toBeDisabled();

		// Resolve the submission
		resolveSubmit?.();

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalled();
		});
	});
});
