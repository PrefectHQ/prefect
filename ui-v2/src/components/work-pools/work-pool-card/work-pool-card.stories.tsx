import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolCard } from "./work-pool-card";

const MOCK_WORK_POOL = createFakeWorkPool();

const meta: Meta<typeof WorkPoolCard> = {
	title: "Components/WorkPools/Card",
	component: WorkPoolCard,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {},
};

export default meta;
type Story = StoryObj<typeof WorkPoolCard>;

export const Default: Story = {
	args: {
		workPool: MOCK_WORK_POOL,
	},
};
