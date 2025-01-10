import type { Meta, StoryObj } from "@storybook/react";

import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { fn } from "@storybook/test";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { ActionStep } from "./action-step";

const MOCK_DATA = [
	createFakeAutomation(),
	createFakeAutomation(),
	createFakeAutomation(),
	createFakeAutomation(),
];

const meta = {
	title: "Components/Automations/Wizard/ActionStep",
	component: ActionStep,
	args: { onSubmit: fn() },
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(MOCK_DATA);
				}),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "ActionStep" };
