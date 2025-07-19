import { QueryClient } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InfrastructureTypeStep } from "./infrastructure-type-step";

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
				variables: { properties: {} },
			},
		},
	},
	"prefect-aws": {
		ecs: {
			type: "ecs",
			display_name: "AWS ECS",
			description: "Execute flow runs on AWS ECS",
			logo_url: "https://example.com/ecs.png",
			is_beta: false,
			default_base_job_configuration: {
				job_configuration: { image: "{{ image }}" },
				variables: { properties: {} },
			},
		},
	},
	"prefect-kubernetes": {
		kubernetes: {
			type: "kubernetes",
			display_name: "Kubernetes",
			description: "Execute flow runs in Kubernetes",
			logo_url: "https://example.com/k8s.png",
			is_beta: true,
			default_base_job_configuration: {
				job_configuration: { image: "{{ image }}" },
				variables: { properties: {} },
			},
		},
	},
};

// Wrapper component with Suspense
const InfrastructureTypeStepWithSuspense = (props: React.ComponentProps<typeof InfrastructureTypeStep>) => (
	<Suspense fallback={<div>Loading...</div>}>
		<InfrastructureTypeStep {...props} />
	</Suspense>
);

describe("InfrastructureTypeStep", () => {
	const mockOnChange = vi.fn();

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

	it("renders infrastructure type cards", async () => {
		const queryClient = new QueryClient();
		render(
			<InfrastructureTypeStepWithSuspense
				value={undefined}
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
			expect(screen.getByText("AWS ECS")).toBeInTheDocument();
			expect(screen.getByText("Kubernetes")).toBeInTheDocument();
		});

		expect(
			screen.getByText("Execute flow runs as subprocesses"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Execute flow runs on AWS ECS"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Execute flow runs in Kubernetes"),
		).toBeInTheDocument();
	});

	it("shows beta badge for beta infrastructure types", async () => {
		const queryClient = new QueryClient();
		render(
			<InfrastructureTypeStepWithSuspense
				value={undefined}
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			const kubernetesBadge = screen.getByText("Beta");
			expect(kubernetesBadge).toBeInTheDocument();
		});
	});

	it("calls onChange when an infrastructure type is selected", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<InfrastructureTypeStepWithSuspense
				value={undefined}
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		const processCard = screen.getByText("Process").closest(".cursor-pointer");
		if (processCard) {
			await user.click(processCard);
		}

		expect(mockOnChange).toHaveBeenCalledWith("process");
	});

	it("highlights the selected infrastructure type", async () => {
		const queryClient = new QueryClient();
		const { rerender } = render(
			<InfrastructureTypeStepWithSuspense
				value="process"
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});

		// Check that process card has selected styling
		const processCard = screen
			.getByText("Process")
			.closest("[data-slot='card']");
		expect(processCard).toHaveClass("border-primary");

		// Change selection to ECS
		rerender(
			<InfrastructureTypeStepWithSuspense
				value="ecs"
				onChange={mockOnChange}
			/>,
		);

		// Check that ECS card now has selected styling
		const ecsCard = screen.getByText("AWS ECS").closest("[data-slot='card']");
		expect(ecsCard).toHaveClass("border-primary");
	});

	it("displays logos when available", async () => {
		const queryClient = new QueryClient();
		render(
			<InfrastructureTypeStepWithSuspense
				value={undefined}
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			const logos = screen.getAllByRole("img");
			expect(logos).toHaveLength(3);
			// Verify all logos are present, order may vary due to sorting
			const srcAttributes = logos.map((logo) => logo.getAttribute("src"));
			expect(srcAttributes).toContain("https://example.com/process.png");
			expect(srcAttributes).toContain("https://example.com/ecs.png");
			expect(srcAttributes).toContain("https://example.com/k8s.png");
		});
	});

	it("handles empty workers response", async () => {
		server.use(
			http.get(
				buildApiUrl("/collections/views/aggregate-worker-metadata"),
				() => {
					return HttpResponse.json({});
				},
			),
		);

		const queryClient = new QueryClient();
		render(
			<InfrastructureTypeStepWithSuspense
				value={undefined}
				onChange={mockOnChange}
			/>,
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => {
			expect(screen.queryByText("Process")).not.toBeInTheDocument();
			expect(screen.queryByText("AWS ECS")).not.toBeInTheDocument();
		});
	});
});
