import type { Meta, StoryObj } from "@storybook/react";
import type { JSX } from "react";
import { Label } from "@/components/ui/label";

import { ICONS, type IconId } from "./constants";
import { Icon } from "./icon";

const meta: Meta<typeof Icon> = {
	title: "UI/Icon",
	component: Icon,
	args: {
		id: "Ban",
	},
	render: () => <IconCatalog />,
};

export default meta;

export const story: StoryObj = { name: "Icon" };

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
