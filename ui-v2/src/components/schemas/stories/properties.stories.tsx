import type { Meta, StoryObj } from "@storybook/react";
import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";
import { TestSchemaForm } from "./utilities";

const userDefinition: PrefectSchemaObject = {
	type: "object",
	title: "User",
	properties: {
		name: {
			type: "string",
			title: "Name",
			description: "The name of the user",
		},
		age: {
			type: "string",
			title: "Birthday",
			description: "The age of the user",
			format: "date",
		},
	},
};

const meta = {
	title: "Components/SchemaForm/Properties",
	component: TestSchemaForm,
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof TestSchemaForm>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		schema: {
			definitions: {
				user: userDefinition,
			},
			type: "object",
			properties: {
				user: {
					title: "User",
					type: "object",
					allOf: [
						{ $ref: "#/definitions/user" },
						{
							type: "object",
							properties: {
								email: {
									type: "string",
									title: "Email",
									description: "The email of the user",
								},
							},
						},
					],
				},
			},
		},
	},
};

export const TypeString: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: "John Doe",
					title: "Name",
					type: "string",
				},
			},
		},
	},
};
TypeString.storyName = "type:string";

export const TypeStringWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: "foo",
					title: "Thing",
					type: "string",
					enum: ["foo", "bar", "baz"],
				},
			},
		},
	},
};
TypeStringWithEnum.storyName = "type:string & enum";

export const TypeStringWithFormatDate: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: "2021-01-01",
					title: "Date",
					type: "string",
					format: "date",
				},
			},
		},
	},
};
TypeStringWithFormatDate.storyName = "type:string & format:date";

export const TypeStringWithFormatDateTime: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: "2021-01-01T00:00:00",
					title: "Date & Time",
					type: "string",
					format: "date-time",
				},
			},
		},
	},
};
TypeStringWithFormatDateTime.storyName = "type:string & format:date-time";

export const TypeStringWithFormatJson: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: JSON.stringify({ foo: "bar" }),
					title: "JSON",
					type: "string",
					format: "json-string",
				},
			},
		},
	},
};
TypeStringWithFormatJson.storyName = "type:string & format:json-string";

export const TypeBoolean: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: true,
					title: "Is Active",
					type: "boolean",
				},
			},
		},
	},
};
TypeBoolean.storyName = "type:boolean";

export const TypeBooleanWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: true,
					title: "Is Active",
					type: "boolean",
					enum: [true, false],
				},
			},
		},
	},
};
TypeBooleanWithEnum.storyName = "type:boolean & enum";

export const TypeInteger: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: 30,
					title: "Age",
					type: "integer",
				},
			},
		},
	},
};
TypeInteger.storyName = "type:integer";

export const TypeIntegerWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: 1,
					title: "Age",
					type: "integer",
					enum: [1, 2, 3],
				},
			},
		},
	},
};
TypeIntegerWithEnum.storyName = "type:integer & enum";

export const TypeNumber: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: 30.5,
					title: "Age",
					type: "number",
				},
			},
		},
	},
};
TypeNumber.storyName = "type:number";

export const TypeNumberWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: 1.5,
					title: "Age",
					type: "number",
					enum: [1.5, 2.5, 3.5],
				},
			},
		},
	},
};
TypeNumberWithEnum.storyName = "type:number & enum";

export const TypeArray: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: ["foo", "bar", "baz"],
					title: "Name",
					type: "array",
					items: {
						type: "string",
					},
				},
			},
		},
	},
};
TypeArray.storyName = "type:array";

export const TypeArrayWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					title: "Name",
					type: "array",
					items: {
						type: "string",
						enum: ["foo", "bar", "baz"],
					},
				},
			},
		},
	},
};
TypeArrayWithEnum.storyName = "type:array & enum";

export const TypeArrayWithPrefix: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: ["foo", true],
					title: "Name",
					type: "array",
					prefixItems: [
						{
							type: "string",
							title: "Prefix String",
							enum: ["tag1", "tag2", "tag3"],
						},
						{
							type: "boolean",
							title: "Boolean",
						},
					],
				},
			},
		},
	},
};
TypeArrayWithPrefix.storyName = "type:array & prefixItems";

export const TypeArrayWithAnyOf: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: [1, "foo"],
					title: "Name",
					type: "array",
					//@ts-expect-error pydantic can create properties without a type
					items: {
						anyOf: [
							{ type: "string" },
							{ type: "number" },
							{ type: "boolean" },
							{
								type: "object",
								properties: {
									foo: { type: "string" },
									bar: { type: "number" },
									baz: { type: "boolean" },
								},
							},
						],
					},
				},
			},
		},
	},
};
TypeArrayWithAnyOf.storyName = "type:array & anyOf";

export const TypeObject: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				name: {
					default: { foo: "bar", baz: true },
					title: "User",
					type: "object",
					properties: {
						first_name: { type: "string", title: "First Name" },
						last_name: { type: "string", title: "Last Name" },
						age: { type: "integer", title: "Age" },
						birthday: { type: "string", title: "Birthday", format: "date" },
					},
					required: ["first_name", "last_name"],
				},
			},
		},
	},
};
TypeObject.storyName = "type:object";

export const TypeObjectWithReference: Story = {
	args: {
		schema: {
			definitions: {
				user: userDefinition,
			},
			type: "object",
			properties: {
				user: {
					title: "User Information",
					$ref: "#/definitions/user",
				},
			},
		},
	},
};
TypeObjectWithReference.storyName = "type:object & reference";

export const TypeObjectWithAnyOfAndReference: Story = {
	args: {
		schema: {
			definitions: {
				user: userDefinition,
			},
			type: "object",
			properties: {
				user: {
					type: "object",
					title: "Identification",
					anyOf: [
						{ $ref: "#/definitions/user" },
						{
							type: "object",
							title: "SSN",
							properties: { ssn: { type: "string", title: "SSN" } },
						},
						{
							type: "object",
							title: "Address",
							properties: {
								address: { type: "string", title: "Address" },
								city: { type: "string", title: "City" },
								state: { type: "string", title: "State" },
								zip: { type: "string", title: "Zip" },
							},
						},
					],
				},
			},
		},
	},
};
TypeObjectWithAnyOfAndReference.storyName = "type:object & anyOf & reference";

export const TypeObjectWithAllOfAndReference: Story = {
	args: {
		schema: {
			definitions: {
				user: userDefinition,
			},
			type: "object",
			properties: {
				user: {
					type: "object",
					title: "User Information",
					allOf: [
						{ $ref: "#/definitions/user" },
						{
							type: "object",
							title: "SSN",
							properties: { ssn: { type: "string", title: "SSN" } },
						},
					],
				},
			},
		},
	},
};
TypeObjectWithAllOfAndReference.storyName = "type:object & allOf & reference";

export const TypeObjectWithPosition: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				third: {
					type: "string",
					title: "Third",
					//@ts-expect-error position isn't part of the schema types
					position: 3,
				},
				first: {
					type: "string",
					title: "First",
					//@ts-expect-error position isn't part of the schema types
					position: 1,
				},
				second: {
					type: "string",
					title: "Second",
					//@ts-expect-error position isn't part of the schema types
					position: 2,
				},
			},
		},
	},
};
TypeObjectWithPosition.storyName = "type:object & position";

export const TypeUnknown: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				//@ts-expect-error pydantic can create properties without a type
				name: {
					title: "Unknown",
				},
			},
		},
	},
};
TypeUnknown.storyName = "type:unknown";

export const TypeUnknownWithEnum: Story = {
	args: {
		schema: {
			type: "object",
			properties: {
				//@ts-expect-error pydantic can create properties without a type
				name: {
					title: "Unknown",
					enum: ["foo", "bar", "baz"],
				},
			},
		},
	},
};
TypeUnknownWithEnum.storyName = "type:unknown & enum";

export const prefectKindJson: Story = {
	args: {
		schema: {
			definitions: {
				user: userDefinition,
			},
			type: "object",
			properties: {
				user: {
					$ref: "#/definitions/user",
				},
			},
		},
		values: {
			user: {
				__prefect_kind: "json",
				value: JSON.stringify(
					{
						name: "John Doe",
					},
					null,
					2,
				),
			},
		},
	},
};
prefectKindJson.storyName = "prefect_kind:json";
