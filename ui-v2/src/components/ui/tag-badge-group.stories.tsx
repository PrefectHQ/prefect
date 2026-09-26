import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group.tsx";

export default {
	title: "UI/TagBadgeGroup",
	component: TagBadgeGroup,
	args: {
		tags: [],
	},
	// To control input value in Stories via useState()
	render: function Render(args: ComponentProps<typeof TagBadgeGroup>) {
		return <TagBadgeGroup {...args} />;
	},
} satisfies Meta<typeof TagBadgeGroup>;

type Story = StoryObj<typeof TagBadgeGroup>;

export const TwoTags: Story = {
	args: { tags: ["testTag", "testTag2"] },
};

export const FourTags: Story = {
	args: { tags: ["testTag", "testTag2", "testTag3", "testTag4"] },
};

export const MaxTagsDisplayed: Story = {
	args: {
		tags: ["testTag", "testTag2", "testTag3", "testTag4"],
		maxTagsDisplayed: 2,
	},
};

export const LimitedWidth: Story = {
	args: {
		tags: [
			"production",
			"daily-etl",
			"team-data-platform",
			"critical",
			"region-us-east-1",
			"backfill",
		],
		onTagsChange: (tags) => console.log(tags),
	},
	decorators: [
		(Story) => (
			<div className="w-72 resize-x overflow-hidden border p-2">
				<Story />
			</div>
		),
	],
};
