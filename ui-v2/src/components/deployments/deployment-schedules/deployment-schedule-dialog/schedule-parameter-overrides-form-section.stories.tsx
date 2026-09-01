import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { fn } from "storybook/test";
import { reactQueryDecorator } from "@/storybook/utils";
import { ScheduleParameterOverridesFormSection } from "./schedule-parameter-overrides-form-section";
import type { ScheduleParameterOverrides } from "./use-schedule-parameter-overrides";

type ParameterSchema = NonNullable<ScheduleParameterOverrides["schema"]>;

const SCHEMA: ParameterSchema = {
	type: "object",
	title: "Parameters",
	properties: {
		name: { type: "string", title: "name" },
		limit: { type: "integer", title: "limit" },
	},
	required: [],
};

const meta = {
	title:
		"Components/Deployments/DeploymentScheduleDialog/ScheduleParameterOverridesFormSection",
	component: ScheduleParameterOverridesFormSection,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/schemas/validate"), () =>
					HttpResponse.json({ valid: true, errors: [] }),
				),
			],
		},
	},
	args: {
		schema: SCHEMA,
		values: {},
		errors: [],
		setValues: fn(),
		validate: fn(() => Promise.resolve(true)),
	},
} satisfies Meta<typeof ScheduleParameterOverridesFormSection>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Empty: Story = {};

export const WithOverrides: Story = {
	args: {
		values: { name: "overridden" },
	},
};

export const WithErrors: Story = {
	args: {
		values: { limit: "not a number" },
		errors: [
			{ index: 0, property: "limit", errors: ["is not of type integer"] },
		],
	},
};

export const WithoutProperties: Story = {
	args: {
		schema: { type: "object", properties: {} } satisfies ParameterSchema,
	},
};
