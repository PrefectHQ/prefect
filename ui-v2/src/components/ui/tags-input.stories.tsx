import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { expect, fn, userEvent, within } from "storybook/test";
import { TagsInput } from "@/components/ui/tags-input";

export default {
	title: "UI/TagsInput",
	component: TagsInput,
	args: {
		value: [],
		onChange: fn(),
	},
	argTypes: {
		className: { control: { disable: true } },
		type: { control: { disable: true } },
	},
	// To control input value in Stories via useState()
	render: function Render(args: ComponentProps<typeof TagsInput>) {
		const [value, setValue] = useState(args?.value as string[]);
		return (
			<TagsInput
				{...args}
				value={value}
				onChange={(x) => {
					if (Array.isArray(x)) {
						setValue(x);
						args?.onChange?.(x);
					}
				}}
			/>
		);
	},
} satisfies Meta<typeof TagsInput>;

type Story = StoryObj<typeof TagsInput>;

export const Empty: Story = {};

export const DefaultValue: Story = {
	args: { value: ["testTag", "testTag2"] },
};

export const TestAddRemove: Story = {
	name: "Test: Add and remove",
	play: async ({ canvasElement, step }) => {
		const canvas = within(canvasElement);
		const tagsInput: HTMLInputElement = canvas.getByRole("textbox");

		await step("Add testTag", async () => {
			await userEvent.type(tagsInput, "testTag");
			await expect(tagsInput.value).toBe("testTag");
			await userEvent.type(tagsInput, "{enter}");
			await expect(tagsInput.value).toBe("");
			await expect(canvas.queryByText("testTag")).not.toBeNull();
		});

		await step("Add testTag2", async () => {
			await userEvent.type(tagsInput, "testTag2{enter}");
		});

		await step("Delete testTag", async () => {
			await userEvent.click(canvas.getAllByRole("button")[0]);
			await expect(canvas.queryByText("testTag")).toBeNull();
		});
	},
};
