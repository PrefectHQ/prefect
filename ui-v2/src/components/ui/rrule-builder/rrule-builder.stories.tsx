import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { RRuleBuilder, type RRuleBuilderProps } from "./rrule-builder";

function Controlled(props: RRuleBuilderProps) {
	const [value, setValue] = useState(props.value);
	return (
		<div className="max-w-lg p-4">
			<RRuleBuilder {...props} value={value} onChange={setValue} />
		</div>
	);
}
const meta = {
	title: "UI/RRuleBuilder",
	component: RRuleBuilder,
	render: (args) => <Controlled {...args} />,
	args: {
		value:
			"DTSTART;TZID=America/Chicago:20261119T090000\nRRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE;BYHOUR=9;BYMINUTE=0;BYSECOND=0",
		timezone: "America/Chicago",
		onChange: () => undefined,
	},
} satisfies Meta<typeof RRuleBuilder>;
export default meta;
type Story = StoryObj<typeof meta>;
export const Weekly: Story = {};
export const Monthly: Story = {
	args: {
		value:
			"DTSTART;TZID=America/Chicago:20261119T090000\nRRULE:FREQ=MONTHLY;BYDAY=FR;BYSETPOS=-1",
	},
};
export const Unsupported: Story = {
	args: {
		value: "DTSTART;TZID=America/Chicago:20261119T090000\nRRULE:FREQ=HOURLY",
	},
};
export const Empty: Story = { args: { value: "" } };
