import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeAutomation, createFakeDeployment } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { RunFlowButton } from "./run-flow-button";

const meta = {
	title: "Components/Deployments/RunFlowButton",
	component: RunFlowButton,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
	args: { deployment: createFakeDeployment() },
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/deployments/:id/create_flow_run"), () => {
					return HttpResponse.json(createFakeAutomation());
				}),
			],
		},
	},
} satisfies Meta<typeof RunFlowButton>;

export default meta;

export const story: StoryObj = { name: "RunFlowButton" };
