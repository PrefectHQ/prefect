import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { WorkPoolEditForm } from "./work-pool-edit-form";

const mockNavigate = vi.fn();
const mockHistoryBack = vi.fn();

type UpdateWorkPoolOptions = {
	onSuccess?: () => void;
	onError?: (error: Error) => void;
};

const mockUpdateWorkPool =
	vi.fn<(data: unknown, options: UpdateWorkPoolOptions) => void>();

vi.mock("@tanstack/react-router", () => ({
	useRouter: () => ({
		navigate: mockNavigate,
		history: {
			back: mockHistoryBack,
		},
	}),
}));

vi.mock("@/api/work-pools", async () => {
	const actual = await vi.importActual("@/api/work-pools");
	return {
		...actual,
		useUpdateWorkPool: () => ({
			updateWorkPool: mockUpdateWorkPool,
			isPending: false,
		}),
	};
});

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("WorkPoolEditForm", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
				mutations: { retry: false },
			},
		});

		vi.clearAllMocks();
	});

	const renderWorkPoolEditForm = (
		workPool = createFakeWorkPool({
			name: "test-work-pool",
			description: "Test description",
			concurrency_limit: 10,
			type: "process",
		}),
	) => {
		return render(
			<QueryClientProvider client={queryClient}>
				<WorkPoolEditForm workPool={workPool} />
			</QueryClientProvider>,
		);
	};

	it("renders all form fields", () => {
		renderWorkPoolEditForm();

		expect(screen.getByLabelText("Name")).toBeInTheDocument();
		expect(screen.getByLabelText("Description (Optional)")).toBeInTheDocument();
		expect(
			screen.getByLabelText("Flow Run Concurrency (Optional)"),
		).toBeInTheDocument();
		expect(screen.getByLabelText("Type")).toBeInTheDocument();
	});

	it("displays work pool name in disabled field", () => {
		renderWorkPoolEditForm();

		const nameInput = screen.getByLabelText("Name");
		expect(nameInput).toHaveValue("test-work-pool");
		expect(nameInput).toBeDisabled();
	});

	it("displays work pool type in disabled field", () => {
		renderWorkPoolEditForm();

		const typeInput = screen.getByLabelText("Type");
		expect(typeInput).toHaveValue("process");
		expect(typeInput).toBeDisabled();
	});

	it("displays description in editable field", () => {
		renderWorkPoolEditForm();

		const descriptionInput = screen.getByLabelText("Description (Optional)");
		expect(descriptionInput).toHaveValue("Test description");
		expect(descriptionInput).not.toBeDisabled();
	});

	it("displays concurrency limit in editable field", () => {
		renderWorkPoolEditForm();

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		expect(concurrencyInput).toHaveValue(10);
		expect(concurrencyInput).not.toBeDisabled();
	});

	it("allows editing description", async () => {
		const user = userEvent.setup();
		renderWorkPoolEditForm();

		const descriptionInput = screen.getByLabelText("Description (Optional)");
		await user.clear(descriptionInput);
		await user.type(descriptionInput, "New description");

		expect(descriptionInput).toHaveValue("New description");
	});

	it("allows editing concurrency limit", async () => {
		const user = userEvent.setup();
		renderWorkPoolEditForm();

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		await user.clear(concurrencyInput);
		await user.type(concurrencyInput, "20");

		expect(concurrencyInput).toHaveValue(20);
	});

	it("handles empty concurrency limit as null", async () => {
		const user = userEvent.setup();
		renderWorkPoolEditForm();

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		await user.clear(concurrencyInput);

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockUpdateWorkPool).toHaveBeenCalled();
			const callArgs = mockUpdateWorkPool.mock.calls[0] as [
				{ name: string; workPool: { concurrency_limit: number | null } },
				UpdateWorkPoolOptions,
			];
			expect(callArgs[0].workPool.concurrency_limit).toBeNull();
		});
	});

	it("calls updateWorkPool on form submission", async () => {
		const user = userEvent.setup();
		renderWorkPoolEditForm();

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockUpdateWorkPool).toHaveBeenCalled();
			const callArgs = mockUpdateWorkPool.mock.calls[0] as [
				{
					name: string;
					workPool: {
						description: string | null;
						concurrency_limit: number | null;
						base_job_template: Record<string, unknown>;
					};
				},
				UpdateWorkPoolOptions,
			];
			expect(callArgs[0].name).toBe("test-work-pool");
			expect(callArgs[0].workPool.description).toBe("Test description");
			expect(callArgs[0].workPool.concurrency_limit).toBe(10);
			expect(callArgs[0].workPool.base_job_template).toBeDefined();
		});
	});

	it("calls router.history.back on cancel", async () => {
		const user = userEvent.setup();
		renderWorkPoolEditForm();

		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(cancelButton);

		expect(mockHistoryBack).toHaveBeenCalled();
	});

	it("shows success toast on successful update", async () => {
		const { toast } = await import("sonner");
		const user = userEvent.setup();

		mockUpdateWorkPool.mockImplementation((_data, options) => {
			options.onSuccess?.();
		});

		renderWorkPoolEditForm();

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith("Work pool updated");
		});
	});

	it("shows error toast on failed update", async () => {
		const { toast } = await import("sonner");
		const user = userEvent.setup();

		mockUpdateWorkPool.mockImplementation((_data, options) => {
			options.onError?.(new Error("Network error"));
		});

		renderWorkPoolEditForm();

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				"Failed to update work pool: Network error",
			);
		});
	});

	it("navigates to work pool page on successful update", async () => {
		const user = userEvent.setup();

		mockUpdateWorkPool.mockImplementation((_data, options) => {
			options.onSuccess?.();
		});

		renderWorkPoolEditForm();

		const saveButton = screen.getByRole("button", { name: "Save" });
		await user.click(saveButton);

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({
				to: "/work-pools/work-pool/$workPoolName",
				params: { workPoolName: "test-work-pool" },
			});
		});
	});

	it("renders with null description", () => {
		const workPool = createFakeWorkPool({
			name: "test-pool",
			description: null,
			concurrency_limit: 5,
			type: "docker",
		});

		render(
			<QueryClientProvider client={queryClient}>
				<WorkPoolEditForm workPool={workPool} />
			</QueryClientProvider>,
		);

		const descriptionInput = screen.getByLabelText("Description (Optional)");
		expect(descriptionInput).toHaveValue("");
	});

	it("renders with null concurrency limit", () => {
		const workPool = createFakeWorkPool({
			name: "test-pool",
			description: "Test",
			concurrency_limit: null,
			type: "kubernetes",
		});

		render(
			<QueryClientProvider client={queryClient}>
				<WorkPoolEditForm workPool={workPool} />
			</QueryClientProvider>,
		);

		const concurrencyInput = screen.getByLabelText(
			"Flow Run Concurrency (Optional)",
		);
		expect(concurrencyInput).toHaveValue(null);
	});

	it("renders Save and Cancel buttons", () => {
		renderWorkPoolEditForm();

		expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
	});

	describe("BaseJobTemplateFormSection", () => {
		it("shows Base Job Template section for non-prefect-agent work pool types", () => {
			const workPool = createFakeWorkPool({
				name: "test-pool",
				description: "Test",
				concurrency_limit: 5,
				type: "process",
			});

			render(
				<QueryClientProvider client={queryClient}>
					<WorkPoolEditForm workPool={workPool} />
				</QueryClientProvider>,
			);

			expect(screen.getByText("Base Job Template")).toBeInTheDocument();
		});

		it("shows Base Job Template section for docker work pool type", () => {
			const workPool = createFakeWorkPool({
				name: "test-pool",
				description: "Test",
				concurrency_limit: 5,
				type: "docker",
			});

			render(
				<QueryClientProvider client={queryClient}>
					<WorkPoolEditForm workPool={workPool} />
				</QueryClientProvider>,
			);

			expect(screen.getByText("Base Job Template")).toBeInTheDocument();
		});

		it("hides Base Job Template section for prefect-agent work pool type", () => {
			const workPool = createFakeWorkPool({
				name: "test-pool",
				description: "Test",
				concurrency_limit: 5,
				type: "prefect-agent",
			});

			render(
				<QueryClientProvider client={queryClient}>
					<WorkPoolEditForm workPool={workPool} />
				</QueryClientProvider>,
			);

			expect(screen.queryByText("Base Job Template")).not.toBeInTheDocument();
		});

		it("includes base_job_template in form submission", async () => {
			const user = userEvent.setup();
			const baseJobTemplate = {
				job_configuration: {
					image: "python:3.9",
				},
				variables: {
					type: "object",
					properties: {},
				},
			};

			const workPool = createFakeWorkPool({
				name: "test-pool",
				description: "Test description",
				concurrency_limit: 5,
				type: "process",
				base_job_template: baseJobTemplate,
			});

			render(
				<QueryClientProvider client={queryClient}>
					<WorkPoolEditForm workPool={workPool} />
				</QueryClientProvider>,
			);

			const saveButton = screen.getByRole("button", { name: "Save" });
			await user.click(saveButton);

			await waitFor(() => {
				expect(mockUpdateWorkPool).toHaveBeenCalledWith(
					{
						name: "test-pool",
						workPool: {
							description: "Test description",
							concurrency_limit: 5,
							base_job_template: baseJobTemplate,
						},
					},
					expect.any(Object),
				);
			});
		});
	});
});
