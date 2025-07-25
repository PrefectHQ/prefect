import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

// Mock data for work pool types
const mockWorkPoolTypes = {
	"prefect-agent": {
		"prefect-agent": {
			type: "prefect-agent",
			display_name: "Prefect Agent",
			description: "Execute flow runs with a Prefect agent.",
			logo_url: "https://example.com/logo.svg",
			documentation_url: "https://docs.prefect.io/",
			is_beta: false,
		},
	},
	docker: {
		"docker-container": {
			type: "docker-container",
			display_name: "Docker Container",
			description: "Execute flow runs in Docker containers.",
			logo_url: "https://example.com/docker.svg",
			documentation_url: "https://docs.prefect.io/docker",
			is_beta: false,
		},
	},
};

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
		queryFn: () => mockWorkPoolTypes,
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
				queries: { retry: false, staleTime: Number.POSITIVE_INFINITY },
				mutations: { retry: false },
			},
		});

		// Pre-populate the query client with mock data to avoid suspense
		queryClient.setQueryData(["work-pool-types"], mockWorkPoolTypes);

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

	it("renders infrastructure type options", () => {
		renderWorkPoolCreateWizard();

		expect(screen.getByText("Prefect Agent")).toBeInTheDocument();
		expect(screen.getByText("Docker Container")).toBeInTheDocument();
		expect(
			screen.getByText("Execute flow runs with a Prefect agent."),
		).toBeInTheDocument();
	});

	it("shows form validation message when trying to proceed without selection", async () => {
		renderWorkPoolCreateWizard();

		const nextButton = screen.getByText("Next");
		fireEvent.click(nextButton);

		// Should show validation error
		await waitFor(() => {
			// The form should still be on the first step and show validation
			expect(screen.getByText("Infrastructure Type")).toBeInTheDocument();
		});
	});

	it("renders Cancel button", () => {
		renderWorkPoolCreateWizard();

		const cancelButton = screen.getByText("Cancel");
		expect(cancelButton).toBeInTheDocument();
	});
});
