import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeWorkPool } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TriggerDetailsWorkPoolStatus } from "./trigger-details-work-pool-status";

const mockWorkPool1 = createFakeWorkPool({ id: "pool-1", name: "my-pool" });
const mockWorkPool2 = createFakeWorkPool({
	id: "pool-2",
	name: "production-pool",
});
const mockWorkPool3 = createFakeWorkPool({
	id: "pool-3",
	name: "staging-pool",
});

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsWorkPoolStatus",
	component: TriggerDetailsWorkPoolStatus,
	decorators: [routerDecorator, reactQueryDecorator],
} satisfies Meta<typeof TriggerDetailsWorkPoolStatus>;

export default meta;

type Story = StoryObj<typeof TriggerDetailsWorkPoolStatus>;

export const AnyWorkPoolReactiveReady: Story = {
	name: "Any work pool - Reactive - Ready",
	args: {
		workPoolIds: [],
		posture: "Reactive",
		status: "READY",
	},
	parameters: {
		msw: {
			handlers: [],
		},
	},
};

export const AnyWorkPoolReactiveNotReady: Story = {
	name: "Any work pool - Reactive - Not Ready",
	args: {
		workPoolIds: [],
		posture: "Reactive",
		status: "NOT_READY",
	},
};

export const AnyWorkPoolReactivePaused: Story = {
	name: "Any work pool - Reactive - Paused",
	args: {
		workPoolIds: [],
		posture: "Reactive",
		status: "PAUSED",
	},
};

export const AnyWorkPoolProactiveWithTime: Story = {
	name: "Any work pool - Proactive - With time",
	args: {
		workPoolIds: [],
		posture: "Proactive",
		status: "PAUSED",
		time: 30,
	},
};

export const SingleWorkPoolReactive: Story = {
	name: "Single work pool - Reactive",
	args: {
		workPoolIds: [mockWorkPool1.id],
		posture: "Reactive",
		status: "READY",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool1]);
				}),
			],
		},
	},
};

export const SingleWorkPoolProactiveWithTime: Story = {
	name: "Single work pool - Proactive - With time",
	args: {
		workPoolIds: [mockWorkPool1.id],
		posture: "Proactive",
		status: "PAUSED",
		time: 60,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool1]);
				}),
			],
		},
	},
};

export const MultipleWorkPoolsReactive: Story = {
	name: "Multiple work pools - Reactive",
	args: {
		workPoolIds: [mockWorkPool1.id, mockWorkPool2.id, mockWorkPool3.id],
		posture: "Reactive",
		status: "NOT_READY",
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([
						mockWorkPool1,
						mockWorkPool2,
						mockWorkPool3,
					]);
				}),
			],
		},
	},
};

export const MultipleWorkPoolsProactiveWithTime: Story = {
	name: "Multiple work pools - Proactive - With time",
	args: {
		workPoolIds: [mockWorkPool1.id, mockWorkPool2.id],
		posture: "Proactive",
		status: "READY",
		time: 3600,
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json([mockWorkPool1, mockWorkPool2]);
				}),
			],
		},
	},
};

export const ProactiveWithLongTime: Story = {
	name: "Proactive - Long time duration",
	args: {
		workPoolIds: [],
		posture: "Proactive",
		status: "NOT_READY",
		time: 86400,
	},
};
