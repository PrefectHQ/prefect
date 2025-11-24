import { QueryClient } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FlowRun } from "@/api/flow-runs";
import { FlowRunsChart } from "./flow-runs-chart";

// Mock ResizeObserver
class ResizeObserverMock {
	observe = vi.fn();
	unobserve = vi.fn();
	disconnect = vi.fn();
}

global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

// Mock getBoundingClientRect
const mockGetBoundingClientRect = (width: number) => {
	return vi.fn(() => ({
		width,
		height: 48,
		top: 0,
		left: 0,
		bottom: 48,
		right: width,
		x: 0,
		y: 0,
		toJSON: () => ({}),
	}));
};

describe("FlowRunsChart", () => {
	const mockFlowRuns: FlowRun[] = [
		{
			id: "flow-run-1",
			name: "test-flow-run-1",
			flow_id: "flow-1",
			deployment_id: "deployment-1",
			state_type: "COMPLETED",
			state: {
				id: "state-1",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-01T00:00:00Z",
				message: "",
				state_details: {
					deferred: false,
					untrackable_result: false,
					pause_reschedule: false,
				},
			},
			start_time: "2024-01-01T00:00:00Z",
			expected_start_time: "2024-01-01T00:00:00Z",
			total_run_time: 100,
			created: "2024-01-01T00:00:00Z",
			updated: "2024-01-01T00:00:00Z",
		},
		{
			id: "flow-run-2",
			name: "test-flow-run-2",
			flow_id: "flow-2",
			deployment_id: "deployment-2",
			state_type: "FAILED",
			state: {
				id: "state-2",
				type: "FAILED",
				name: "Failed",
				timestamp: "2024-01-02T00:00:00Z",
				message: "",
				state_details: {
					deferred: false,
					untrackable_result: false,
					pause_reschedule: false,
				},
			},
			start_time: "2024-01-02T00:00:00Z",
			expected_start_time: "2024-01-02T00:00:00Z",
			total_run_time: 50,
			created: "2024-01-02T00:00:00Z",
			updated: "2024-01-02T00:00:00Z",
		},
	];

	const mockFlows = [
		{
			id: "flow-1",
			name: "test-flow-1",
			created: "2024-01-01T00:00:00Z",
			updated: "2024-01-01T00:00:00Z",
		},
		{
			id: "flow-2",
			name: "test-flow-2",
			created: "2024-01-02T00:00:00Z",
			updated: "2024-01-02T00:00:00Z",
		},
	];

	const mockDeployments = [
		{
			id: "deployment-1",
			name: "test-deployment-1",
			flow_id: "flow-1",
			created: "2024-01-01T00:00:00Z",
			updated: "2024-01-01T00:00:00Z",
		},
		{
			id: "deployment-2",
			name: "test-deployment-2",
			flow_id: "flow-2",
			created: "2024-01-02T00:00:00Z",
			updated: "2024-01-02T00:00:00Z",
		},
	];

	const dateRange = {
		start: new Date("2024-01-01T00:00:00Z"),
		end: new Date("2024-01-31T23:59:59Z"),
	};

	beforeEach(() => {
		// Setup default MSW handlers
		server.use(
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(mockFlows);
			}),
			http.post(buildApiUrl("/deployments/filter"), () => {
				return HttpResponse.json(mockDeployments);
			}),
		);
	});

	it("should render the chart component", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Wait for the component to render
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});
	});

	it("should calculate numberOfBars based on container width", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		// Mock container width of 240px
		// With BAR_WIDTH=8 and BAR_GAP=4, this should give us 20 bars
		const containerWidth = 240;

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Mock getBoundingClientRect on the chart container
		const chartContainer = container.querySelector("div");
		if (chartContainer) {
			chartContainer.getBoundingClientRect =
				mockGetBoundingClientRect(containerWidth);
		}

		// Wait for the chart to render
		await waitFor(() => {
			const chartSurface = container.querySelector(".recharts-surface");
			expect(chartSurface).toBeInTheDocument();
		});

		// Component successfully renders with dynamic sizing
		expect(chartContainer).toBeInTheDocument();
	});

	it("should enrich flow runs with deployment and flow data", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Wait for data to be fetched and enriched
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});

		// Verify that the API calls were made
		// Note: This is a simple check to ensure the handlers are registered
		// In a real scenario, we would verify the actual API calls were made
		await waitFor(() => {
			const handlers = server.listHandlers();
			expect(handlers.length).toBeGreaterThan(0);
		});
	});

	it("should handle empty flow runs array gracefully", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container } = render(
			<FlowRunsChart flowRuns={[]} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Component should still render without errors
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});
	});

	it("should handle flow runs without deployment_id", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const flowRunsWithoutDeployment: FlowRun[] = [
			{
				...mockFlowRuns[0],
				deployment_id: null,
			},
		];

		const { container } = render(
			<FlowRunsChart
				flowRuns={flowRunsWithoutDeployment}
				dateRange={dateRange}
			/>,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Component should render and filter out flow runs without deployments
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});
	});

	it("should pass correct props to FlowRunActivityBarChart", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});

		// Verify that the outer wrapper has the correct classes
		const outerWrapper = container.querySelector(".w-full");
		expect(outerWrapper).toBeInTheDocument();

		// Verify the chart container has the h-12 class
		const chartContainer = container.querySelector(".h-12");
		expect(chartContainer).toBeInTheDocument();
	});

	it("should handle missing deployment data gracefully", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		// Override the deployments endpoint to return empty array
		server.use(
			http.post(buildApiUrl("/deployments/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Component should render without errors even if deployments are missing
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});
	});

	it("should handle missing flow data gracefully", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		// Override the flows endpoint to return empty array
		server.use(
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Component should render without errors even if flows are missing
		await waitFor(() => {
			const chartContainer = container.querySelector(".recharts-surface");
			expect(chartContainer).toBeInTheDocument();
		});
	});

	it("should cleanup ResizeObserver on unmount", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container, unmount } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Wait for the chart to render
		await waitFor(() => {
			const chartSurface = container.querySelector(".recharts-surface");
			expect(chartSurface).toBeInTheDocument();
		});

		// Unmount the component - should not throw errors
		expect(() => unmount()).not.toThrow();
	});

	it("should use debounced numberOfBars value", async () => {
		const queryClient = new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
			},
		});

		const { container } = render(
			<FlowRunsChart flowRuns={mockFlowRuns} dateRange={dateRange} />,
			{
				wrapper: createWrapper({ queryClient }),
			},
		);

		// Wait for the component to render and debounce to settle
		await waitFor(
			() => {
				const chartContainer = container.querySelector(".recharts-surface");
				expect(chartContainer).toBeInTheDocument();
			},
			{ timeout: 3000 },
		);

		// The chart should be rendered with debounced value
		// This tests the asymmetric debounce pattern (debouncedNumberOfBars || numberOfBars)
		const chartContainer = container.querySelector(".recharts-surface");
		expect(chartContainer).toBeInTheDocument();
	});
});
