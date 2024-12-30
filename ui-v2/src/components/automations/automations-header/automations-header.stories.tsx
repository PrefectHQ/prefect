import { routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { AutomationsHeader } from "./automations-header";

const meta = {
	title: "Components/Automations/AutomationsHeader",
	component: AutomationsHeader,
	decorators: [routerDecorator],
} satisfies Meta<typeof AutomationsHeader>;

export default meta;

export const Story: StoryObj = {
	name: "AutomationsHeader",
};
