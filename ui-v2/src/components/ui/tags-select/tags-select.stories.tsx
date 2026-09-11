import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { TagsSelect } from "./tags-select";

const SUGGESTIONS = [
	"nightly",
	"production",
	"staging",
	"team-a",
	"team-b",
] as const;

export default {
	title: "UI/TagsSelect",
	component: TagsSelect,
	args: {
		suggestions: [...SUGGESTIONS],
		value: [],
	},
	// To control the selected tags in Stories via useState()
	render: function Render({
		value,
		...args
	}: ComponentProps<typeof TagsSelect>) {
		const [tags, setTags] = useState<string[]>(value ?? []);
		return (
			<div className="w-72">
				<TagsSelect {...args} value={tags} onChange={setTags} />
			</div>
		);
	},
} satisfies Meta<typeof TagsSelect>;

type Story = StoryObj<typeof TagsSelect>;

export const Default: Story = {
	args: { placeholder: "Filter by tags" },
};

export const WithSelectedTags: Story = {
	args: { value: ["production", "team-a"] },
};

export const WithoutSuggestions: Story = {
	args: { suggestions: [] },
};
