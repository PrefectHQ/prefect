import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import { createFakeDeployment } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { DeploymentScheduleDialog } from "./deployment-schedule-dialog";

const MOCK_DEPLOYMENT = createFakeDeployment({
	parameter_openapi_schema: {
		type: "object",
		title: "Parameters",
		properties: {
			name: { type: "string", title: "name", position: 0 },
			limit: { type: "integer", title: "limit", position: 1 },
		},
		required: ["name"],
	},
	parameters: { name: "marvin", limit: 10 },
});

const meta = {
	title: "Components/Deployments/DeploymentScheduleDialog",
	component: DeploymentScheduleDialog,
	decorators: [toastDecorator, routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/schemas/validate"), () =>
					HttpResponse.json({ valid: true, errors: [] }),
				),
				http.post(buildApiUrl("/deployments/:id/schedules"), () =>
					HttpResponse.json([], { status: 201 }),
				),
				http.patch(
					buildApiUrl("/deployments/:id/schedules/:schedule_id"),
					() => new HttpResponse(null, { status: 204 }),
				),
			],
		},
	},
	args: {
		deployment: MOCK_DEPLOYMENT,
		open: true,
		onOpenChange: fn(),
		onSubmit: fn(),
	},
} satisfies Meta<typeof DeploymentScheduleDialog>;

export default meta;

type Story = StoryObj<typeof meta>;

export const CreateSchedule: Story = {};

export const EditSchedule: Story = {
	args: {
		scheduleToEdit: {
			id: "schedule-id",
			created: new Date().toISOString(),
			updated: new Date().toISOString(),
			deployment_id: MOCK_DEPLOYMENT.id,
			active: true,
			max_scheduled_runs: null,
			schedule: { cron: "1 * * * *", timezone: "UTC", day_or: true },
			parameters: { name: "overridden" },
		},
	},
};

export const WithoutParameters: Story = {
	args: {
		deployment: createFakeDeployment({
			parameter_openapi_schema: { type: "object", properties: {} },
		}),
	},
};
