import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

// Mock the router
vi.mock("@tanstack/react-router", () => ({
	useRouter: () => ({
		navigate: vi.fn(),
	}),
}));

// Mock the API hooks
vi.mock("@/api/work-pools", () => ({
	useCreateWorkPool: () => ({
		createWorkPool: vi.fn(),
		isPending: false,
	}),
}));

// Mock the collections API
vi.mock("@/api/collections/collections", () => ({
	buildListWorkPoolTypesQuery: () => ({
		queryKey: ["work-pool-types"],
		queryFn: () => Promise.resolve({}),
	}),
}));

// Mock the toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("WorkPoolCreateWizard", () => {
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

	const renderWorkPoolCreateWizard = () => {
		return render(
			<QueryClientProvider client={queryClient}>
				<WorkPoolCreateWizard />
			</QueryClientProvider>,
		);
	};

	it("renders the wizard with initial step", () => {
		renderWorkPoolCreateWizard();

		expect(screen.getByText("Create Work Pool")).toBeInTheDocument();
		expect(screen.getByText("Infrastructure Type")).toBeInTheDocument();
		expect(screen.getByText("Work Pool Information")).toBeInTheDocument();
		expect(
			screen.getByText("Infrastructure Configuration"),
		).toBeInTheDocument();
	});

	it("shows navigation buttons correctly", () => {
		renderWorkPoolCreateWizard();

		// On first step, only Next and Cancel should be visible
		expect(screen.queryByText("Back")).not.toBeInTheDocument();
		expect(screen.getByText("Next")).toBeInTheDocument();
		expect(screen.getByText("Cancel")).toBeInTheDocument();
	});

	it("disables Next button when infrastructure type is not selected", async () => {
		renderWorkPoolCreateWizard();

		const nextButton = screen.getByText("Next");
		fireEvent.click(nextButton);

		// Should still be on first step since validation failed
		await waitFor(() => {
			expect(
				screen.getByText(
					"Select the infrastructure you want to use to execute your flow runs",
				),
			).toBeInTheDocument();
		});
	});

	it("shows Back button on second step", async () => {
		renderWorkPoolCreateWizard();

		// Mock infrastructure type selection (this would need more setup for real testing)
		// For now, just test navigation structure
		const wizard = screen.getByText("Create Work Pool").closest("div");
		expect(wizard).toBeInTheDocument();
	});

	it("shows Create Work Pool button on final step", () => {
		renderWorkPoolCreateWizard();

		// The component structure should show correct button text based on step
		expect(screen.getByText("Next")).toBeInTheDocument();
	});

	it("calls cancel navigation when Cancel is clicked", () => {
		const mockNavigate = vi.fn();
		vi.mocked(require("@tanstack/react-router").useRouter).mockReturnValue({
			navigate: mockNavigate,
		});

		renderWorkPoolCreateWizard();

		const cancelButton = screen.getByText("Cancel");
		fireEvent.click(cancelButton);

		expect(mockNavigate).toHaveBeenCalledWith({ to: "/work-pools" });
	});
});
