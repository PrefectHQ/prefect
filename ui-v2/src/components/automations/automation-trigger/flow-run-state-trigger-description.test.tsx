import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AutomationTrigger } from "@/components/automations/trigger-details";
import { FlowRunStateTriggerDescription } from "./flow-run-state-trigger-description";

vi.mock("@/components/flows/flow-icon-text", () => ({
	FlowIconText: ({ flowId }: { flowId: string }) => (
		<span data-testid="flow-icon-text">{flowId}</span>
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

type ResourceSpecification = { [key: string]: string | string[] };

function createFlowRunStateTrigger(
	overrides: Partial<{
		posture: "Reactive" | "Proactive";
		expect: string[];
		after: string[];
		within: number;
		match_related: ResourceSpecification[];
	}> = {},
): AutomationTrigger {
	const posture = overrides.posture ?? "Reactive";
	return {
		type: "event",
		posture,
		match: {
			"prefect.resource.id": "prefect.flow-run.*",
		},
		match_related: overrides.match_related ?? [],
		for_each: ["prefect.resource.id"],
		expect: posture === "Reactive" ? (overrides.expect ?? []) : [],
		after: posture === "Proactive" ? (overrides.after ?? []) : [],
		threshold: 1,
		within: overrides.within ?? 0,
	};
}

describe("FlowRunStateTriggerDescription", () => {
	it("renders basic text for any flow run", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("When any flow run")).toBeInTheDocument();
		expect(screen.getByText("enters")).toBeInTheDocument();
	});

	it("renders 'any state' when states array is empty", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: [],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("any state")).toBeInTheDocument();
	});

	it("renders state badges when states are provided", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed", "prefect.flow-run.Failed"],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("Completed")).toBeInTheDocument();
		expect(screen.getByText("Failed")).toBeInTheDocument();
	});

	it("renders 'stays in' for Proactive posture", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Running"],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("stays in")).toBeInTheDocument();
	});

	it("renders time for Proactive posture using secondsToString format", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Running"],
			within: 30,
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
	});

	it("renders longer time correctly with secondsToString format", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Running"],
			within: 3600,
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("for 1 hour")).toBeInTheDocument();
	});

	it("does not render time for Reactive posture", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
			within: 30,
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
	});

	it("renders flow icon text when flowIds are provided", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.flow-id-1",
						"prefect.flow.flow-id-2",
					],
				},
			],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("of flow")).toBeInTheDocument();
		expect(screen.getAllByTestId("flow-icon-text")).toHaveLength(2);
		expect(screen.getByText("or")).toBeInTheDocument();
	});

	it("renders 'or' separator correctly for multiple flows", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.flow-id-1",
						"prefect.flow.flow-id-2",
						"prefect.flow.flow-id-3",
					],
				},
			],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		const orElements = screen.getAllByText("or");
		expect(orElements).toHaveLength(1);
	});

	it("renders tags when provided", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Failed"],
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.tag.production",
						"prefect.tag.critical",
					],
				},
			],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("with tags")).toBeInTheDocument();
		expect(screen.getByText("production")).toBeInTheDocument();
		expect(screen.getByText("critical")).toBeInTheDocument();
	});

	it("does not render flow section when flowIds is empty", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.queryByText("of flow")).not.toBeInTheDocument();
	});

	it("does not render tags section when tags is empty", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Reactive",
			expect: ["prefect.flow-run.Completed"],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.queryByText("with tags")).not.toBeInTheDocument();
	});

	it("renders complex trigger with all options", () => {
		const trigger = createFlowRunStateTrigger({
			posture: "Proactive",
			after: ["prefect.flow-run.Failed", "prefect.flow-run.Crashed"],
			within: 60,
			match_related: [
				{
					"prefect.resource.id": [
						"prefect.flow.flow-id-1",
						"prefect.tag.production",
					],
				},
			],
		});

		render(<FlowRunStateTriggerDescription trigger={trigger} />, {
			wrapper: QueryWrapper,
		});

		expect(screen.getByText("When any flow run")).toBeInTheDocument();
		expect(screen.getByText("of flow")).toBeInTheDocument();
		expect(screen.getByText("with tags")).toBeInTheDocument();
		expect(screen.getByText("stays in")).toBeInTheDocument();
		expect(screen.getByText("Failed")).toBeInTheDocument();
		expect(screen.getByText("Crashed")).toBeInTheDocument();
		expect(screen.getByText(/for 1 minute/)).toBeInTheDocument();
	});

	it("returns null for non-event triggers", () => {
		const compoundTrigger = {
			type: "compound" as const,
			require: "all" as const,
			triggers: [],
			within: null,
		};

		const { container } = render(
			<FlowRunStateTriggerDescription trigger={compoundTrigger} />,
			{ wrapper: QueryWrapper },
		);

		expect(container.firstChild).toBeNull();
	});
});
