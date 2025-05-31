import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { WorkPoolForm } from "./work-pool-form";
import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";

const meta: Meta<typeof WorkPoolForm> = {
  title: "Components/WorkPools/WorkPoolForm",
  component: WorkPoolForm,
  decorators: [routerDecorator, reactQueryDecorator],
};
export default meta;

type Story = StoryObj<typeof WorkPoolForm>;

export const Create: Story = {};

export const Edit: Story = {
  args: {
    workPool: createFakeWorkPool(),
  },
};
