import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { AutomationWizard } from "./automation-wizard";

const MOCK_AUTOMATIONS_DATA = Array.from({ length: 5 }, createFakeAutomation);

const meta = {
	title: "Components/Automations/Wizard/AutomationWizard",
	component: AutomationWizard,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(MOCK_AUTOMATIONS_DATA);
				}),
			],
		},
	},
} satisfies Meta<typeof AutomationWizard>;

export default meta;

type Story = StoryObj<typeof AutomationWizard>;

export const CreateAutomation: Story = {};
