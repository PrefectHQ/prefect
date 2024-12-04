import type { Meta, StoryObj } from "@storybook/react";

import { Icon } from "@/components/ui/icons";
import { Button } from "./button";
import { DocsLink } from "./docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "./empty-state";

const meta: Meta<typeof EmptyState> = {
	title: "UI/EmptyState",
	component: EmptyState,
	parameters: {
		docs: {
			description: {
				component:
					"EmptyState is used to prompt to user to create a resource when there is none",
			},
		},
	},
};
export default meta;

type Story = StoryObj<typeof EmptyState>;
export const Usage: Story = {
	render: () => <EmptyStateExample />,
};

function EmptyStateExample(): JSX.Element {
	return (
		<EmptyState>
			<EmptyStateIcon id="Variable" />
			<EmptyStateTitle>Add a variable to get started</EmptyStateTitle>
			<EmptyStateDescription>
				Variables store non-sensitive pieces of JSON.
			</EmptyStateDescription>
			<EmptyStateActions>
				<Button onClick={console.log}>
					Add Variable <Icon id="Plus" className="h-4 w-4 ml-2" />
				</Button>
				<DocsLink id="variables-guide" />
			</EmptyStateActions>
		</EmptyState>
	);
}
