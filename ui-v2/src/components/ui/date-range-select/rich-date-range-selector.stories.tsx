import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import {
	type DateRangeSelectValue,
	RichDateRangeSelector,
} from "./rich-date-range-selector";

const meta: Meta<typeof RichDateRangeSelector> = {
	title: "UI/RichDateRangeSelector",
	component: RichDateRangeSelector,
};
export default meta;

type Story = StoryObj<typeof RichDateRangeSelector>;

export const Basic: Story = {
	render: () => {
		function BasicStory() {
			const [value, setValue] = useState<DateRangeSelectValue>(null);
			return (
				<div className="p-4">
					<RichDateRangeSelector
						value={value}
						onValueChange={setValue}
						clearable
					/>
				</div>
			);
		}
		return <BasicStory />;
	},
};
