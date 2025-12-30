import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeFlow } from "@/mocks";
import { TriggerDetails } from "./trigger-details";
import type { AutomationTrigger } from "./trigger-utils";

const TriggerDetailsRouter = ({ trigger }: { trigger: AutomationTrigger }) => {
	const rootRoute = createRootRoute({
		component: () => <TriggerDetails trigger={trigger} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

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
				wrapper: createWrapper(),
			});

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
		});

		it("renders flow run state trigger with proactive posture", () => {
			render(<TriggerDetails trigger={flowRunStateTriggerProactive} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("stays in")).toBeInTheDocument();
		});

		it("renders flow run state trigger with specific flow", async () => {
			const mockFlow = createFakeFlow({
				id: "my-flow-id",
				name: "My Test Flow",
			});

			server.use(
				http.get(buildApiUrl("/flows/:id"), () => {
					return HttpResponse.json(mockFlow);
				}),
			);

			await waitFor(() =>
				render(<TriggerDetailsRouter trigger={flowRunStateTriggerWithFlow} />, {
					wrapper: createWrapper(),
				}),
			);

			expect(screen.getByText("When any flow run")).toBeInTheDocument();
			expect(screen.getByText("of flow")).toBeInTheDocument();

			await waitFor(() => {
				expect(screen.getByText("My Test Flow")).toBeInTheDocument();
			});
		});
	});

	describe("Deployment Status Trigger", () => {
		it("renders deployment status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={deploymentStatusTriggerReactive} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any deployment")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders deployment status trigger with not-ready status", () => {
			render(<TriggerDetails trigger={deploymentStatusTriggerNotReady} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("Work Pool Status Trigger", () => {
		it("renders work pool status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={workPoolStatusTriggerReactive} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any work pool")).toBeInTheDocument();
			expect(screen.getByText("enters")).toBeInTheDocument();
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders work pool status trigger with not-ready status", () => {
			render(<TriggerDetails trigger={workPoolStatusTriggerNotReady} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("Work Queue Status Trigger", () => {
		it("renders work queue status trigger with reactive posture", () => {
			render(<TriggerDetails trigger={workQueueStatusTriggerReactive} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any work queue")).toBeInTheDocument();
		});
	});

	describe("Compound Trigger", () => {
		it("renders compound trigger with require all", () => {
			render(<TriggerDetails trigger={compoundTriggerAll} />, {
				wrapper: createWrapper(),
			});

			expect(
				screen.getByText(
					/compound trigger requiring all of 2 nested triggers/i,
				),
			).toBeInTheDocument();
		});

		it("renders compound trigger with require any", () => {
			render(<TriggerDetails trigger={compoundTriggerAny} />, {
				wrapper: createWrapper(),
			});

			expect(
				screen.getByText(
					/compound trigger requiring any of 2 nested triggers/i,
				),
			).toBeInTheDocument();
		});

		it("renders compound trigger with require number", () => {
			render(<TriggerDetails trigger={compoundTriggerNumber} />, {
				wrapper: createWrapper(),
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
				wrapper: createWrapper(),
			});

			expect(
				screen.getByText(/sequence trigger with 2 nested triggers/i),
			).toBeInTheDocument();
			expect(screen.getByText(/must fire in order/i)).toBeInTheDocument();
		});

		it("renders sequence trigger with single trigger", () => {
			render(<TriggerDetails trigger={sequenceTriggerSingle} />, {
				wrapper: createWrapper(),
			});

			expect(
				screen.getByText(/sequence trigger with 1 nested trigger/i),
			).toBeInTheDocument();
		});
	});

	describe("Custom Trigger", () => {
		it("renders custom trigger", () => {
			render(<TriggerDetails trigger={customTrigger} />, {
				wrapper: createWrapper(),
			});

			expect(screen.getByText("A custom trigger")).toBeInTheDocument();
		});
	});
});
