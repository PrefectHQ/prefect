import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import type { Event } from "@/api/events";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
	createFakeTaskRun,
	createFakeTaskRunConcurrencyLimit,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { EventResourceDisplay } from "./event-resource-display";
import {
	AutomationResourceDisplay,
	BlockDocumentResourceDisplay,
	ConcurrencyLimitResourceDisplay,
	DeploymentResourceDisplay,
	FlowResourceDisplay,
	FlowRunResourceDisplay,
	TaskRunResourceDisplay,
	WorkPoolResourceDisplay,
	WorkQueueResourceDisplay,
} from "./resource-displays";

const createMockEvent = (resourceId: string, resourceName?: string): Event => ({
	id: "test-event-id",
	occurred: new Date().toISOString(),
	event: "test.event",
	resource: {
		"prefect.resource.id": resourceId,
		...(resourceName ? { "prefect.resource.name": resourceName } : {}),
	},
	related: [],
	payload: {},
	received: new Date().toISOString(),
});

const mockFlowRun = createFakeFlowRun({
	id: "flow-run-123",
	name: "my-flow-run",
});
const mockTaskRun = createFakeTaskRun({
	id: "task-run-123",
	name: "my-task-run",
});
const mockDeployment = createFakeDeployment({
	id: "deployment-123",
	name: "my-deployment",
});
const mockFlow = createFakeFlow({ id: "flow-123", name: "my-flow" });
const mockWorkPool = createFakeWorkPool({
	id: "work-pool-123",
	name: "my-work-pool",
});
const mockWorkQueue = createFakeWorkQueue({
	id: "work-queue-123",
	name: "my-work-queue",
});
const mockAutomation = createFakeAutomation({
	id: "automation-123",
	name: "my-automation",
});
const mockBlockDocument = createFakeBlockDocument({
	id: "block-document-123",
	name: "my-block",
});
const mockConcurrencyLimit = createFakeTaskRunConcurrencyLimit({
	id: "concurrency-limit-123",
	tag: "my-concurrency-limit",
});

const meta = {
	title: "Components/Events/EventResourceDisplay",
	component: EventResourceDisplay,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof EventResourceDisplay>;

export default meta;
type Story = StoryObj<typeof EventResourceDisplay>;

export const WithResourceName: Story = {
	args: {
		event: createMockEvent("prefect.flow-run.abc-123", "My Flow Run"),
	},
};

export const WithoutResourceNameFetchesFromAPI: Story = {
	args: {
		event: createMockEvent("prefect.flow-run.flow-run-123"),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(mockFlowRun);
				}),
			],
		},
	},
};

export const UnknownResourceType: Story = {
	args: {
		event: createMockEvent("some.unknown.resource"),
	},
};

export const NoResourceInformation: Story = {
	args: {
		event: {
			id: "test-event-id",
			occurred: new Date().toISOString(),
			event: "test.event",
			resource: {},
			related: [],
			payload: {},
			received: new Date().toISOString(),
		},
	},
};

export const FlowRunDisplay: StoryObj<typeof FlowRunResourceDisplay> = {
	render: () => <FlowRunResourceDisplay resourceId="flow-run-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(mockFlowRun);
				}),
			],
		},
	},
};

export const TaskRunDisplay: StoryObj<typeof TaskRunResourceDisplay> = {
	render: () => <TaskRunResourceDisplay resourceId="task-run-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(mockTaskRun);
				}),
			],
		},
	},
};

export const DeploymentDisplay: StoryObj<typeof DeploymentResourceDisplay> = {
	render: () => <DeploymentResourceDisplay resourceId="deployment-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/deployments/:id"), () => {
					return HttpResponse.json(mockDeployment);
				}),
			],
		},
	},
};

export const FlowDisplay: StoryObj<typeof FlowResourceDisplay> = {
	render: () => <FlowResourceDisplay resourceId="flow-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flows/:id"), () => {
					return HttpResponse.json(mockFlow);
				}),
			],
		},
	},
};

export const WorkPoolDisplay: StoryObj<typeof WorkPoolResourceDisplay> = {
	render: () => <WorkPoolResourceDisplay resourceId="work-pool-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/work_pools/:name"), () => {
					return HttpResponse.json(mockWorkPool);
				}),
			],
		},
	},
};

export const WorkQueueDisplay: StoryObj<typeof WorkQueueResourceDisplay> = {
	render: () => <WorkQueueResourceDisplay resourceId="work-queue-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/work_queues/:id"), () => {
					return HttpResponse.json(mockWorkQueue);
				}),
			],
		},
	},
};

export const AutomationDisplay: StoryObj<typeof AutomationResourceDisplay> = {
	render: () => <AutomationResourceDisplay resourceId="automation-123" />,
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/automations/:id"), () => {
					return HttpResponse.json(mockAutomation);
				}),
			],
		},
	},
};

export const BlockDocumentDisplay: StoryObj<
	typeof BlockDocumentResourceDisplay
> = {
	render: () => (
		<BlockDocumentResourceDisplay resourceId="block-document-123" />
	),
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/block_documents/:id"), () => {
					return HttpResponse.json(mockBlockDocument);
				}),
			],
		},
	},
};

export const ConcurrencyLimitDisplay: StoryObj<
	typeof ConcurrencyLimitResourceDisplay
> = {
	render: () => (
		<ConcurrencyLimitResourceDisplay resourceId="concurrency-limit-123" />
	),
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/concurrency_limits/:id"), () => {
					return HttpResponse.json(mockConcurrencyLimit);
				}),
			],
		},
	},
};
