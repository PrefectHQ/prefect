import type { Meta, StoryObj } from "@storybook/react";

import { Typography } from "./typography";

const meta: Meta<typeof Typography> = {
	title: "UI/Typography",
	component: Typography,
	parameters: {
		docs: {
			description: {
				component: "Typography is used as your basic text component",
			},
		},
	},
	render: () => {
		return (
			<div>
				<Typography variant="h1">h1 Typography</Typography>
				<Typography variant="h2">h2 Typography</Typography>
				<Typography variant="h3">h3 Typography</Typography>
				<Typography variant="h4">h4 Typography</Typography>
				<Typography variant="bodyLarge">bodyLarge Typography</Typography>
				<Typography variant="body">body Typography</Typography>
				<Typography variant="bodySmall">bodySmall Typography</Typography>
			</div>
		);
	},
};
export default meta;

export const story: StoryObj = { name: "Typography" };
