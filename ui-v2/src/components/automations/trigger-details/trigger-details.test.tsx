import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TriggerDetails } from "./trigger-details";
import type { AutomationTrigger } from "./trigger-utils";

vi.mock("@/components/flows/flow-link", () => ({
	FlowLink: ({ flowId }: { flowId: string }) => (
		<span data-testid="flow-link">{flowId}</span>
	),
}));

vi.mock("@/components/deployments/deployment-link", () => ({
	DeploymentLink: ({ deploymentId }: { deploymentId: string }) => (
		<span data-testid="deployment-link">{deploymentId}</span>
	),
}));

vi.mock("@/components/work-pools/work-pool-link", () => ({
	WorkPoolLink: ({ workPoolName }: { workPoolName: string }) => (
		<span data-testid="work-pool-link">{workPoolName}</span>
	),
}));

vi.mock("@/components/work-pools/work-queue-icon-text", () => ({
	WorkQueueIconText: ({
		workPoolName,
		workQueueName,
	}: {
		workPoolName: string;
		workQueueName: string;
	}) => (
		<span data-testid="work-queue-link">
			{workPoolName}/{workQueueName}
		</span>
	),
}));

vi.mock("@/api/work-pools", () => ({
	buildFilterWorkPoolsQuery: () => ({
		queryKey: ["work-pools"],
		queryFn: () => Promise.resolve([]),
	}),
}));

vi.mock("@/api/work-queues", () => ({
	buildGetWorkQueueQuery: (id: string) => ({
		queryKey: ["work-queue", id],
		queryFn: () =>
			Promise.resolve({
				id,
				name: `queue-${id}`,
				work_pool_name: "test-pool",
			}),
	}),
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

const flowRunStateTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const flowRunStateTriggerProactive: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {},
	after: ["prefect.flow-run.Running"],
	expect: [],
	for_each: ["prefect.resource.id"],
	posture: "Proactive",
	threshold: 1,
	within: 60,
};

const flowRunStateTriggerWithFlow: AutomationTrigger = {
	type: "event",
	id: "trigger-1",
	match: {
		"prefect.resource.id": "prefect.flow-run.*",
	},
	match_related: {
		"prefect.resource.role": "flow",
		"prefect.resource.id": "prefect.flow.my-flow-id",
	},
	after: [],
	expect: ["prefect.flow-run.Completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const deploymentStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-2",
	match: {
		"prefect.resource.id": "prefect.deployment.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.deployment.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const deploymentStatusTriggerNotReady: AutomationTrigger = {
	type: "event",
	id: "trigger-2",
	match: {
		"prefect.resource.id": "prefect.deployment.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.deployment.not-ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const workPoolStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-3",
	match: {
		"prefect.resource.id": "prefect.work-pool.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.work-pool.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const workPoolStatusTriggerNotReady: AutomationTrigger = {
	type: "event",
	id: "trigger-3",
	match: {
		"prefect.resource.id": "prefect.work-pool.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.work-pool.not-ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const workQueueStatusTriggerReactive: AutomationTrigger = {
	type: "event",
	id: "trigger-4",
	match: {
		"prefect.resource.id": "prefect.work-queue.*",
	},
	match_related: {},
	after: [],
	expect: ["prefect.work-queue.ready"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 1,
	within: 0,
};

const compoundTriggerAll: AutomationTrigger = {
	type: "compound",
	require: "all",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const compoundTriggerAny: AutomationTrigger = {
	type: "compound",
	require: "any",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const compoundTriggerNumber: AutomationTrigger = {
	type: "compound",
	require: 2,
	triggers: [
		flowRunStateTriggerReactive,
		deploymentStatusTriggerReactive,
		workPoolStatusTriggerReactive,
	],
	within: 60,
};

const sequenceTrigger: AutomationTrigger = {
	type: "sequence",
	triggers: [flowRunStateTriggerReactive, deploymentStatusTriggerReactive],
	within: 60,
};

const sequenceTriggerSingle: AutomationTrigger = {
	type: "sequence",
	triggers: [flowRunStateTriggerReactive],
	within: 60,
};

const customTrigger: AutomationTrigger = {
	type: "event",
	id: "trigger-custom",
	match: {
		"prefect.resource.id": "custom.resource.*",
	},
	match_related: {},
	after: ["custom.event.started"],
	expect: ["custom.event.completed"],
	for_each: ["prefect.resource.id"],
	posture: "Reactive",
	threshold: 5,
	within: 300,
};

describe("TriggerDetails", () => {
	describe("Flow Run State Trigger", () => {
		it("renders flow run state trigger with reactive posture", () => {
			render(<TriggerDetails trigger={flowRunStateTriggerReactive} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
		});

		it("renders flow run state trigger with proactive posture", () => {
			render(<TriggerDetails trigger={flowRunStateTriggerProactive} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("stays in")).toBeInTheDocument();
		});

		it("renders flow run state trigger with specific flow", () => {
			render(<TriggerDetails trigger={flowRunStateTriggerWithFlow} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("of flow")).toBeInTheDocument();
			expect(screen.getByTestId("flow-link")).toHaveTextContent("my-flow-id");
		});
	});

	describe("Deployment Status Trigger", () => {
		it("renders deployment status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={deploymentStatusTriggerReactive} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any deployment")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders deployment status trigger with not-ready status", () => {
			render(<TriggerDetails trigger={deploymentStatusTriggerNotReady} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("Work Pool Status Trigger", () => {
		it("renders work pool status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={workPoolStatusTriggerReactive} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any work pool")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders work pool status trigger with not-ready status", () => {
			render(<TriggerDetails trigger={workPoolStatusTriggerNotReady} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("Work Queue Status Trigger", () => {
		it("renders work queue status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={workQueueStatusTriggerReactive} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any work queue")).toBeInTheDocument();
		});
	});

	describe("Compound Trigger", () => {
		it("renders compound trigger with require all", () => {
			render(<TriggerDetails trigger={compoundTriggerAll} />, {
				wrapper: QueryWrapper,
			});

			expect(
				screen.getByText(
					/compound trigger requiring all of 2 nested triggers/i,
				),
			).toBeInTheDocument();
		});

		it("renders compound trigger with require any", () => {
			render(<TriggerDetails trigger={compoundTriggerAny} />, {
				wrapper: QueryWrapper,
			});

			expect(
				screen.getByText(
					/compound trigger requiring any of 2 nested triggers/i,
				),
			).toBeInTheDocument();
		});

		it("renders compound trigger with require number", () => {
			render(<TriggerDetails trigger={compoundTriggerNumber} />, {
				wrapper: QueryWrapper,
			});

			expect(
				screen.getByText(
					/compound trigger requiring at least 2 of 3 nested triggers/i,
				),
			).toBeInTheDocument();
		});
	});

	describe("Sequence Trigger", () => {
		it("renders sequence trigger", () => {
			render(<TriggerDetails trigger={sequenceTrigger} />, {
				wrapper: QueryWrapper,
			});

			expect(
				screen.getByText(/sequence trigger with 2 nested triggers/i),
			).toBeInTheDocument();
			expect(screen.getByText(/must fire in order/i)).toBeInTheDocument();
		});

		it("renders sequence trigger with single trigger", () => {
			render(<TriggerDetails trigger={sequenceTriggerSingle} />, {
				wrapper: QueryWrapper,
			});

			expect(
				screen.getByText(/sequence trigger with 1 nested trigger/i),
			).toBeInTheDocument();
		});
	});

	describe("Custom Trigger", () => {
		it("renders custom trigger", () => {
			render(<TriggerDetails trigger={customTrigger} />, {
				wrapper: QueryWrapper,
			});

			expect(screen.getByText("A custom trigger")).toBeInTheDocument();
		});
	});
});
