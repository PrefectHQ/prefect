import { createFakeWorkQueue } from "@/mocks/create-fake-work-queue";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { WorkQueueDetailsHeader } from "./work-queue-details-header";

const meta: Meta<typeof WorkQueueDetailsHeader> = {
  title: "Components/WorkPools/WorkQueueDetailsHeader",
  component: WorkQueueDetailsHeader,
  decorators: [routerDecorator, reactQueryDecorator],
};
export default meta;

type Story = StoryObj<typeof WorkQueueDetailsHeader>;

export const Default: Story = {
  args: {
    workPoolName: "my-pool",
    workQueue: createFakeWorkQueue({ work_pool_name: "my-pool" }),
  },
};
