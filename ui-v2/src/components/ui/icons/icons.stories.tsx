import { Label } from "@/components/ui/label";
import type { Meta, StoryObj } from "@storybook/react";

import { ICONS, type IconId } from "./constants";
import { Icon } from "./icon";

const meta: Meta<typeof Icon> = {
	title: "UI/Icon",
	component: Icon,
	args: {
		id: "Ban",
	},
};

export default meta;

type Story = StoryObj<typeof Icon>;

export const Icons: Story = {
	render: () => <IconCatalog />,
};

function IconCatalog(): JSX.Element {
	return (
		<div
			style={{
				display: "grid",
				gridTemplateColumns: "repeat(4, 1fr)",
				rowGap: "1em",
			}}
		>
			{Object.keys(ICONS).map((id) => {
				return (
					<div key={id} className="flex flex-col items-center gap-1">
						<div>
							<Label>{id}</Label>
						</div>
						<div>
							<Icon id={id as IconId} />
						</div>
					</div>
				);
			})}
		</div>
	);
}

export const Usage: Story = {
	args: { id: "Ban" },
};
