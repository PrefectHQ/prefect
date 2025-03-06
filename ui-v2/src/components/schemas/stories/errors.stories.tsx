import type { Meta, StoryObj } from "@storybook/react";
import { TestSchemaForm } from "./utilities";

const meta = {
	title: "Components/SchemaForm/Errors",
	component: TestSchemaForm,
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof TestSchemaForm>;

export default meta;

type Story = StoryObj<typeof meta>;

export const PropertyError: Story = {
	args: {
		schema: {
			type: "object",
			required: ["name"],
			properties: {
				name: { type: "string", title: "Name" },
			},
		},
		errors: [{ property: "name", errors: ["Name is required"] }],
	},
};

export const PropertyErrors: Story = {
	args: {
		schema: {
			type: "object",
			required: ["name"],
			properties: {
				name: { type: "string", title: "Name" },
			},
		},
		errors: [
			{ property: "name", errors: ["Name must be a string"] },
			{ property: "name", errors: ["Name is required"] },
		],
	},
};

export const ArrayErrors: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				values: {
					type: "array",
					default: ["", "foo", "bar"],
					title: "Values",
					items: {
						type: "string",
						title: "Value",
					},
				},
			},
		},
		errors: [
			{
				property: "values",
				errors: [
					"Values is not valid",
					{ index: 0, errors: ["Value must not be empty"] },
					{ index: 2, errors: ["Value must not be bar"] },
				],
			},
		],
	},
};

export const ObjectErrors: Story = {
	args: {
		schema: {
			type: "object",
			required: ["name"],
			properties: {
				user: {
					title: "User",
					type: "object",
					properties: {
						name: { type: "string", title: "Name" },
						age: { type: "number", title: "Age" },
					},
				},
			},
		},
		errors: [
			{
				property: "user",
				errors: [
					"User is not valid",
					{ property: "name", errors: ["Name is required"] },
					{ property: "age", errors: ["Age must be a number"] },
				],
			},
		],
	},
};
