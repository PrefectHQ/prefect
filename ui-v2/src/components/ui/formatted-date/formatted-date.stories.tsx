import type { Meta, StoryObj } from "@storybook/react";

import { FormattedDate } from "./formatted-date";

const meta: Meta<typeof FormattedDate> = {
	title: "UI/FormattedDate",
	component: FormattedDate,
	parameters: {
		layout: "centered",
	},
	argTypes: {
		format: {
			control: "select",
			options: ["relative", "absolute", "both"],
		},
		showTooltip: {
			control: "boolean",
		},
	},
};

export default meta;
type Story = StoryObj<typeof FormattedDate>;

const recentDate = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(); // 2 hours ago
const oldDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(); // 30 days ago

export const Relative: Story = {
	args: {
		date: recentDate,
		format: "relative",
	},
};

export const Absolute: Story = {
	args: {
		date: recentDate,
		format: "absolute",
	},
};

export const Both: Story = {
	args: {
		date: recentDate,
		format: "both",
	},
};

export const WithoutTooltip: Story = {
	args: {
		date: recentDate,
		format: "relative",
		showTooltip: false,
	},
};

export const NullDate: Story = {
	args: {
		date: null,
	},
};

export const InvalidDate: Story = {
	args: {
		date: "invalid-date-string",
	},
};

export const OldDate: Story = {
	args: {
		date: oldDate,
		format: "relative",
	},
};

export const AllFormats: Story = {
	render: () => (
		<div className="space-y-4">
			<div className="space-y-2">
				<h3 className="font-semibold">Recent Date (2 hours ago)</h3>
				<div className="grid grid-cols-1 gap-2">
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Relative:</span>
						<FormattedDate date={recentDate} format="relative" />
					</div>
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Absolute:</span>
						<FormattedDate date={recentDate} format="absolute" />
					</div>
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Both:</span>
						<FormattedDate date={recentDate} format="both" />
					</div>
				</div>
			</div>

			<div className="space-y-2">
				<h3 className="font-semibold">Old Date (30 days ago)</h3>
				<div className="grid grid-cols-1 gap-2">
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Relative:</span>
						<FormattedDate date={oldDate} format="relative" />
					</div>
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Absolute:</span>
						<FormattedDate date={oldDate} format="absolute" />
					</div>
				</div>
			</div>

			<div className="space-y-2">
				<h3 className="font-semibold">Edge Cases</h3>
				<div className="grid grid-cols-1 gap-2">
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Null:</span>
						<FormattedDate date={null} />
					</div>
					<div className="flex items-center space-x-2">
						<span className="w-20 text-sm font-medium">Invalid:</span>
						<FormattedDate date="invalid" />
					</div>
				</div>
			</div>
		</div>
	),
};
