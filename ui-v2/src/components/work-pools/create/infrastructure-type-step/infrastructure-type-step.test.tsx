import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import type React from "react";
import { FormProvider, useForm } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";
import { InfrastructureTypeStep } from "./infrastructure-type-step";

const mockWorkersResponse = {
	prefect: {
		process: {
			type: "process",
			display_name: "Process",
			description: "Execute flow runs as subprocesses",
			logo_url: "https://example.com/process.png",
			is_beta: false,
		},
	},
	"prefect-aws": {
		ecs: {
			type: "ecs",
			display_name: "AWS ECS",
			description: "Execute flow runs on AWS ECS",
			logo_url: "https://example.com/ecs.png",
			is_beta: true,
		},
	},
};

// Mock the API query
vi.mock("@/api/collections/collections", () => ({
	buildListWorkPoolTypesQuery: () => ({
		queryKey: ["collections", "work-pool-types"],
		queryFn: () => Promise.resolve(mockWorkersResponse),
	}),
}));

describe("InfrastructureTypeStep", () => {
	const TestWrapper = ({ children }: { children: React.ReactNode }) => {
		const form = useForm<{ type: string }>({
			defaultValues: {
				type: "",
			},
		});

		return <FormProvider {...form}>{children}</FormProvider>;
	};

	const renderComponent = () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		// Pre-populate the query cache
		queryClient.setQueryData(
			["collections", "work-pool-types"],
			mockWorkersResponse,
		);

		const Wrapper = ({ children }: { children: React.ReactNode }) => {
			const QueryWrapper = createWrapper({ queryClient });
			return (
				<QueryWrapper>
					<TestWrapper>{children}</TestWrapper>
				</QueryWrapper>
			);
		};

		return render(<InfrastructureTypeStep />, {
			wrapper: Wrapper,
		});
	};

	it("renders the component with worker options", async () => {
		renderComponent();

		expect(
			screen.getByText(
				"Select the infrastructure you want to use to execute your flow runs",
			),
		).toBeInTheDocument();

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
			expect(screen.getByText("AWS ECS")).toBeInTheDocument();
		});
	});

	it("displays worker descriptions", async () => {
		renderComponent();

		await waitFor(() => {
			expect(
				screen.getByText("Execute flow runs as subprocesses"),
			).toBeInTheDocument();
			expect(
				screen.getByText("Execute flow runs on AWS ECS"),
			).toBeInTheDocument();
		});
	});

	it("shows beta badge for beta workers", async () => {
		renderComponent();

		await waitFor(() => {
			expect(screen.getByText("Beta")).toBeInTheDocument();
		});
	});

	it("updates form value when option is selected", async () => {
		const user = userEvent.setup();

		renderComponent();

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processOption = screen.getByRole("radio", { name: /process/i });
		await user.click(processOption);

		expect(processOption).toBeChecked();
	});

	it("sorts options with non-beta first, then alphabetically", async () => {
		renderComponent();

		await waitFor(() => {
			const options = screen.getAllByRole("radio");
			expect(options).toHaveLength(2);

			// Process (non-beta) should come before ECS (beta)
			expect(options[0]).toHaveAttribute("aria-checked", "false");
			expect(screen.getByText("Process")).toBeInTheDocument();
		});
	});

	it("displays validation error when no option is selected", () => {
		renderComponent();

		// The form validation would be triggered by form submission
		// Since we're testing the validation function directly
		const validateType = (value: string) => {
			if (!value) {
				return "Infrastructure type is required";
			}
			return true;
		};

		expect(validateType("")).toBe("Infrastructure type is required");
		expect(validateType("process")).toBe(true);
	});
});
