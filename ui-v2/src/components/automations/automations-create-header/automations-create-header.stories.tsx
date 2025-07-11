import type { Meta, StoryObj } from "@storybook/react";
import { routerDecorator } from "@/storybook/utils";

import { AutomationsCreateHeader } from "./automations-create-header";

const meta = {
	title: "Components/Automations/AutomationsCreateHeader",
	component: AutomationsCreateHeader,
	decorators: [routerDecorator],
} satisfies Meta<typeof AutomationsCreateHeader>;

export default meta;

export const Story: StoryObj = {
	name: "AutomationsCreateHeader",
};
