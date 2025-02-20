import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { CronInput } from "./cron-input";

const meta: Meta<typeof CronInput> = {
	title: "UI/CronInput",
	render: () => <CronInputStory />,
};

export default meta;

export const story: StoryObj = { name: "CronInput" };

const CronInputStory = () => {
	const [input, setInput] = useState("* * * * *");

	return <CronInput value={input} onChange={(e) => setInput(e.target.value)} />;
};
