import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import type { EventsCount } from "@/api/events";
import { routerDecorator } from "@/storybook/utils";
import { EventsLineChart } from "./events-line-chart";

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

const meta = {
	title: "Components/Events/EventsLineChart",
	component: EventsLineChart,
	parameters: {
		layout: "centered",
	},
	args: {
		data: [],
	},
	decorators: [routerDecorator],
	render: function Render(args: ComponentProps<typeof EventsLineChart>) {
		return <EventsLineChart {...args} className="h-64 w-[600px]" />;
	},
} satisfies Meta<typeof EventsLineChart>;

export default meta;
type Story = StoryObj<typeof EventsLineChart>;

export const Default: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "random"),
	},
};

export const IncreasingTrend: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "increasing"),
	},
};

export const DecreasingTrend: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "decreasing"),
	},
};

export const WithSpike: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "spike"),
	},
};

export const Empty: Story = {
	args: {
		data: [],
	},
};

export const SingleDataPoint: Story = {
	args: {
		data: [createMockEventsCount(now, 42)],
	},
};

export const HighVolume: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 48, "random").map((item) => ({
			...item,
			count: item.count * 100,
		})),
	},
};

export const HiddenAxis: Story = {
	args: {
		data: generateMockData(twentyFourHoursAgo, 24, "random"),
		showAxis: false,
	},
};
