import type { Meta, StoryObj } from "@storybook/react";
import { createFakeWorkQueue } from "@/mocks";
import { routerDecorator } from "@/storybook/utils";
import { reactQueryDecorator } from "@/storybook/utils/react-query-decorator";
import { TriggerDetailsWorkQueueStatus } from "./trigger-details-work-queue-status";

const MOCK_WORK_QUEUE_1 = createFakeWorkQueue({
	id: "work-queue-1",
	name: "default",
	work_pool_name: "my-work-pool",
});

const MOCK_WORK_QUEUE_2 = createFakeWorkQueue({
	id: "work-queue-2",
	name: "high-priority",
	work_pool_name: "my-work-pool",
});

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsWorkQueueStatus",
	component: TriggerDetailsWorkQueueStatus,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				// Mock work queue fetch by ID
				{
					method: "GET",
					path: "/api/work_queues/:id",
					response: ({ params }: { params: { id: string } }) => {
						if (params.id === "work-queue-1") {
							return MOCK_WORK_QUEUE_1;
						}
						if (params.id === "work-queue-2") {
							return MOCK_WORK_QUEUE_2;
						}
						return null;
					},
				},
			],
		},
	},
} satisfies Meta<typeof TriggerDetailsWorkQueueStatus>;

export default meta;

type Story = StoryObj<typeof TriggerDetailsWorkQueueStatus>;

export const SingleWorkQueueSingleWorkPool: Story = {
	name: "Single Work Queue + Single Work Pool",
	args: {
		workQueueIds: ["work-queue-1"],
		workPoolNames: ["my-work-pool"],
		posture: "Reactive",
		status: "READY",
	},
};

export const MultipleWorkQueuesMultipleWorkPools: Story = {
	name: "Multiple Work Queues + Multiple Work Pools",
	args: {
		workQueueIds: ["work-queue-1", "work-queue-2"],
		workPoolNames: ["my-work-pool", "another-work-pool"],
		posture: "Reactive",
		status: "NOT_READY",
	},
};

export const AnyWorkQueue: Story = {
	name: "Any Work Queue (Empty Arrays)",
	args: {
		workQueueIds: [],
		workPoolNames: [],
		posture: "Reactive",
		status: "PAUSED",
	},
};

export const ReactivePosture: Story = {
	name: "Reactive Posture",
	args: {
		workQueueIds: ["work-queue-1"],
		workPoolNames: ["my-work-pool"],
		posture: "Reactive",
		status: "READY",
	},
};

export const ProactivePostureWithTime: Story = {
	name: "Proactive Posture With Time",
	args: {
		workQueueIds: ["work-queue-1"],
		workPoolNames: ["my-work-pool"],
		posture: "Proactive",
		status: "READY",
		time: 30,
	},
};

export const ProactivePostureWithLongerTime: Story = {
	name: "Proactive Posture With Longer Time",
	args: {
		workQueueIds: ["work-queue-1"],
		workPoolNames: ["my-work-pool"],
		posture: "Proactive",
		status: "NOT_READY",
		time: 3661,
	},
};

export const ProactivePostureWithoutTime: Story = {
	name: "Proactive Posture Without Time",
	args: {
		workQueueIds: ["work-queue-1"],
		workPoolNames: ["my-work-pool"],
		posture: "Proactive",
		status: "PAUSED",
	},
};

export const StatusReady: Story = {
	name: "Status: Ready",
	args: {
		workQueueIds: [],
		workPoolNames: [],
		posture: "Reactive",
		status: "READY",
	},
};

export const StatusNotReady: Story = {
	name: "Status: Not Ready",
	args: {
		workQueueIds: [],
		workPoolNames: [],
		posture: "Reactive",
		status: "NOT_READY",
	},
};

export const StatusPaused: Story = {
	name: "Status: Paused",
	args: {
		workQueueIds: [],
		workPoolNames: [],
		posture: "Reactive",
		status: "PAUSED",
	},
};
