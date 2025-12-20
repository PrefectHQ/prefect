import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeFlow } from "@/mocks";
import { routerDecorator, toastDecorator } from "@/storybook/utils";
import { FlowPageHeader } from "./flow-page-header";

const meta = {
	title: "Components/Flows/FlowPageHeader",
	component: FlowPageHeader,
	decorators: [toastDecorator, routerDecorator],
	args: {
		onDelete: fn(),
	},
} satisfies Meta<typeof FlowPageHeader>;

export default meta;
type Story = StoryObj<typeof FlowPageHeader>;

export const Default: Story = {
	args: {
		flow: createFakeFlow({
			name: "my-etl-flow",
		}),
	},
};

export const LongFlowName: Story = {
	args: {
		flow: createFakeFlow({
			name: "my-very-long-flow-name-that-might-cause-wrapping-issues-in-the-breadcrumb",
		}),
	},
};

export const FlowWithTags: Story = {
	args: {
		flow: createFakeFlow({
			name: "tagged-flow",
			tags: ["production", "etl", "daily"],
		}),
	},
};

export const FlowWithLabels: Story = {
	args: {
		flow: createFakeFlow({
			name: "labeled-flow",
			labels: { environment: "production", team: "data-engineering" },
		}),
	},
};

export const SimpleFlowName: Story = {
	args: {
		flow: createFakeFlow({
			name: "flow",
		}),
	},
};
