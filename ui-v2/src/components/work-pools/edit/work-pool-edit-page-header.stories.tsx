import type { Meta, StoryObj } from "@storybook/react";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { WorkPoolEditPageHeader } from "./work-pool-edit-page-header";

const meta: Meta<typeof WorkPoolEditPageHeader> = {
	title: "Components/WorkPools/WorkPoolEditPageHeader",
	component: WorkPoolEditPageHeader,
	decorators: [reactQueryDecorator, routerDecorator],
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolEditPageHeader>;

export const Default: Story = {
	args: {
		workPool: createFakeWorkPool({ name: "my-work-pool" }),
	},
};

export const LongName: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "very-long-work-pool-name-that-might-wrap-or-truncate-in-the-breadcrumb",
		}),
	},
};

export const ShortName: Story = {
	args: {
		workPool: createFakeWorkPool({ name: "dev" }),
	},
};

export const NameWithSpecialCharacters: Story = {
	args: {
		workPool: createFakeWorkPool({ name: "my-pool_v2.0" }),
	},
};

export const KubernetesWorkPool: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "production-kubernetes-pool",
			type: "kubernetes",
		}),
	},
};
