import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeLog, createFakeTaskRun } from "@/mocks";

import { RunLogs } from ".";

export default {
	title: "UI/RunLogs",
	component: (args) => (
		<div className="w-screen h-screen">
			<RunLogs {...args} />
		</div>
	),
} satisfies Meta<typeof RunLogs>;

type Story = StoryObj<typeof RunLogs>;

export const logs: Story = {
	name: "RunLogs",
	args: {
		logs: Array.from({ length: 100 }, () => createFakeLog()).sort((a, b) =>
			a.timestamp.localeCompare(b.timestamp),
		),
		taskRun: createFakeTaskRun(),
		onBottomReached: fn(),
	},
};

export const noLogs: Story = {
	args: {
		logs: [],
		taskRun: createFakeTaskRun(),
		onBottomReached: fn(),
	},
};

const ESC = String.fromCharCode(27);

export const ansiColors: Story = {
	name: "RunLogs (ANSI colors)",
	args: {
		logs: [
			createFakeLog({
				message: `${ESC}[32mgreen${ESC}[0m ${ESC}[31mred${ESC}[0m plain`,
			}),
			createFakeLog({
				message: `${ESC}[1m${ESC}[34mbold blue${ESC}[0m and ${ESC}[3m${ESC}[33myellow italic${ESC}[0m`,
			}),
			createFakeLog({
				message: `${ESC}[36mvisit https://example.com for details${ESC}[0m`,
			}),
		].sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
		taskRun: createFakeTaskRun(),
		onBottomReached: fn(),
	},
};
