import type { Meta, StoryObj } from "@storybook/react";

import { useState } from "react";
import { TimezoneSelect } from "./timezone-select";

const meta: Meta<typeof TimezoneSelect> = {
	title: "UI/TimezoneSelect",
	component: () => <TimezoneSelectStory />,
};
export default meta;

export const story: StoryObj = { name: "TimezoneSelect" };

const TimezoneSelectStory = () => {
	const [value, setValue] = useState("America/Los_Angeles");
	return <TimezoneSelect selectedValue={value} onSelect={setValue} />;
};
