import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { WorkPoolDetailsHeader } from "./work-pool-details-header";

const meta: Meta<typeof WorkPoolDetailsHeader> = {
  title: "Components/WorkPools/WorkPoolDetailsHeader",
  component: WorkPoolDetailsHeader,
  decorators: [routerDecorator, reactQueryDecorator],
};
export default meta;

type Story = StoryObj<typeof WorkPoolDetailsHeader>;

export const Default: Story = {
  args: {
    workPool: createFakeWorkPool(),
  },
};
