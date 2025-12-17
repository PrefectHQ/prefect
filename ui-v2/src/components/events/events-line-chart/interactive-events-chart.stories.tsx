import type { Meta, StoryObj } from "@storybook/react";
import type { EventsCount } from "@/api/events";
import { routerDecorator } from "@/storybook/utils";
import { InteractiveEventsChart } from "./interactive-events-chart";

const createMockEventsCount = (
	startTime: Date,
	count: number,
	label?: string,
): EventsCount => ({
	value: startTime.toISOString(),
	start_time: startTime.toISOString(),
	end_time: new Date(startTime.getTime() + 3600000).toISOString(),
	count,
	label: label ?? `${count} events`,
});

const generateMockData = (
	startDate: Date,
	hours: number,
	pattern: "random" | "increasing" | "decreasing" | "spike" = "random",
): EventsCount[] => {
	return Array.from({ length: hours }, (_, i) => {
		const time = new Date(startDate.getTime() + i * 3600000);
		let count: number;

		switch (pattern) {
			case "increasing":
				count = Math.floor(i * 10 + Math.random() * 20);
				break;
			case "decreasing":
				count = Math.floor((hours - i) * 10 + Math.random() * 20);
				break;
			case "spike":
				count =
					i === Math.floor(hours / 2)
						? 200
						: Math.floor(Math.random() * 30 + 10);
				break;
			default:
				count = Math.floor(Math.random() * 100 + 10);
		}

		return createMockEventsCount(time, count);
	});
};

const now = new Date();
const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

const meta = {
	title: "Components/Events/InteractiveEventsChart",
	component: InteractiveEventsChart,
	parameters: {
		layout: "centered",
	},
	decorators: [routerDecorator],
} satisfies Meta<typeof InteractiveEventsChart>;

export default meta;
type Story = StoryObj<typeof InteractiveEventsChart>;

export const Default: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "random"),
		className: "h-64 w-[600px]",
		startDate: twentyFourHoursAgo,
		endDate: now,
	},
};

export const WithIncreasingTrend: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "increasing"),
		className: "h-64 w-[600px]",
		startDate: twentyFourHoursAgo,
		endDate: now,
	},
};

export const WithSpike: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "spike"),
		className: "h-64 w-[600px]",
		startDate: twentyFourHoursAgo,
		endDate: now,
	},
};

export const WeekRange: Story = {
	args: {
		data: generateMockData(oneWeekAgo, 168, "random"), // 168 hours = 1 week
		className: "h-64 w-[600px]",
		startDate: oneWeekAgo,
		endDate: now,
	},
};

export const Empty: Story = {
	args: {
		data: [],
		className: "h-64 w-[600px]",
		startDate: twentyFourHoursAgo,
		endDate: now,
	},
};
