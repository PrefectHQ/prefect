import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeDeployment, createFakeFlowRun } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { QuickRunParametersDialog } from "./quick-run-parameters-dialog";

const meta = {
	title: "Components/Deployments/QuickRunParametersDialog",
	component: QuickRunParametersDialog,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
	args: {
		open: true,
		onOpenChange: () => {},
		deployment: createFakeDeployment({
			enforce_parameter_schema: true,
			parameter_openapi_schema: {
				title: "Parameters",
				type: "object",
				properties: {
					project: {
						title: "Project",
						type: "string",
					},
					region: {
						title: "Region",
						type: "string",
						default: "us-east-1",
					},
				},
				required: ["project"],
			},
			parameters: { region: "us-east-1" },
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/schemas/validate"), () =>
					HttpResponse.json({ valid: true, errors: [] }),
				),
				http.post(buildApiUrl("/deployments/:id/create_flow_run"), () =>
					HttpResponse.json(createFakeFlowRun()),
				),
			],
		},
	},
} satisfies Meta<typeof QuickRunParametersDialog>;

export default meta;

export const story: StoryObj = { name: "QuickRunParametersDialog" };
