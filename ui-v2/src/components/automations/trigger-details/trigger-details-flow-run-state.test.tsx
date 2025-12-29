import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TriggerDetailsFlowRunState } from "./trigger-details-flow-run-state";

// Mock FlowLink since it requires async data fetching
vi.mock("@/components/flows/flow-link", () => ({
	FlowLink: ({ flowId }: { flowId: string }) => (
		<span data-testid="flow-link">{flowId}</span>
	),
}));

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: false,
		},
	},
});

function QueryWrapper({ children }: { children: React.ReactNode }) {
	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}

describe("TriggerDetailsFlowRunState", () => {
	it("renders basic text for any flow run", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("When any flow run")).toBeInTheDocument();
		expect(screen.getByText("enters")).toBeInTheDocument();
	});

	it("renders 'any state' when states array is empty", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={[]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("any state")).toBeInTheDocument();
	});

	it("renders state badges when states are provided", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED", "FAILED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("Completed")).toBeInTheDocument();
		expect(screen.getByText("Failed")).toBeInTheDocument();
	});

	it("renders 'stays in' for Proactive posture", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Proactive"
				states={["RUNNING"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("stays in")).toBeInTheDocument();
	});

	it("renders time for Proactive posture", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Proactive"
				states={["RUNNING"]}
				time={30}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("for 30s")).toBeInTheDocument();
	});

	it("renders longer time correctly", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Proactive"
				states={["RUNNING"]}
				time={3600}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("for 1h 0m")).toBeInTheDocument();
	});

	it("does not render time for Reactive posture", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
				time={30}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
	});

	it("renders flow links when flowIds are provided", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={["flow-id-1", "flow-id-2"]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("of flow")).toBeInTheDocument();
		expect(screen.getAllByTestId("flow-link")).toHaveLength(2);
		expect(screen.getByText("or")).toBeInTheDocument();
	});

	it("renders 'or' separator correctly for multiple flows", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={["flow-id-1", "flow-id-2", "flow-id-3"]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		// Should have "or" between second-to-last and last flow
		const orElements = screen.getAllByText("or");
		expect(orElements).toHaveLength(1);
	});

	it("renders tags when provided", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={["production", "critical"]}
				posture="Reactive"
				states={["FAILED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("with the tag")).toBeInTheDocument();
		expect(screen.getByText("production")).toBeInTheDocument();
		expect(screen.getByText("critical")).toBeInTheDocument();
	});

	it("does not render flow section when flowIds is empty", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.queryByText("of flow")).not.toBeInTheDocument();
	});

	it("does not render tags section when tags is empty", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={[]}
				tags={[]}
				posture="Reactive"
				states={["COMPLETED"]}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.queryByText("with the tag")).not.toBeInTheDocument();
	});

	it("renders complex trigger with all options", () => {
		render(
			<TriggerDetailsFlowRunState
				flowIds={["flow-id-1"]}
				tags={["production"]}
				posture="Proactive"
				states={["FAILED", "CRASHED"]}
				time={60}
			/>,
			{ wrapper: QueryWrapper },
		);

		expect(screen.getByText("When any flow run")).toBeInTheDocument();
		expect(screen.getByText("of flow")).toBeInTheDocument();
		expect(screen.getByText("with the tag")).toBeInTheDocument();
		expect(screen.getByText("stays in")).toBeInTheDocument();
		expect(screen.getByText("Failed")).toBeInTheDocument();
		expect(screen.getByText("Crashed")).toBeInTheDocument();
		expect(screen.getByText(/for 1m/)).toBeInTheDocument();
	});
});
