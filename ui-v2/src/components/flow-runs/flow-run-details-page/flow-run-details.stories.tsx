import type { Meta, StoryObj } from "@storybook/react";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunDetails } from "./flow-run-details";

export default {
	title: "Components/FlowRuns/FlowRunDetails",
	component: FlowRunDetails,
	parameters: {
		layout: "centered",
	},
} satisfies Meta<typeof FlowRunDetails>;

type Story = StoryObj<typeof FlowRunDetails>;

export const FullData: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "abc123-def456-ghi789",
			run_count: 3,
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			created_by: {
				id: "user-123",
				type: "USER",
				display_value: "John Doe",
			},
			idempotency_key: "my-unique-key-12345",
			tags: ["production", "critical", "daily-etl", "high-priority"],
			flow_version: "v2.1.0",
			state: {
				id: "state-id",
				type: "COMPLETED",
				name: "Completed",
				timestamp: new Date().toISOString(),
				message: "Flow completed successfully after 3 retries",
			},
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0,
				retries: 3,
				retry_delay: 60,
				pause_keys: [],
				resuming: false,
				retry_type: null,
			},
		}),
	},
};

export const MinimalData: Story = {
	args: {
		flowRun: createFakeFlowRun({
			id: "minimal-flow-run-id",
			run_count: 1,
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			created_by: null,
			idempotency_key: null,
			tags: [],
			flow_version: null,
			state: {
				id: "state-id",
				type: "RUNNING",
				name: "Running",
				timestamp: new Date().toISOString(),
				message: null,
			},
			empirical_policy: {
				max_retries: 0,
				retry_delay_seconds: 0,
				retries: null,
				retry_delay: null,
				pause_keys: [],
				resuming: false,
				retry_type: null,
			},
		}),
	},
};

export const NoFlowRun: Story = {
	args: {
		flowRun: null,
	},
};
