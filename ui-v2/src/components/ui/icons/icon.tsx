import type { LucideProps } from "lucide-react";
import { ICONS, type IconId } from "./constants";

type IconProps = {
	id: IconId;
} & LucideProps;

export const Icon = ({ id, ...rest }: IconProps) => {
	const IconComponent = ICONS[id];
	return <IconComponent {...rest} />;
};
