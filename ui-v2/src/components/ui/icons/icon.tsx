import { type LucideProps } from "lucide-react";
import { ICONS, type IconId } from "./constants";

type Props = {
	id: IconId;
} & LucideProps;

export const Icon = ({ id, ...rest }: Props) => {
	const IconComponent = ICONS[id];
	return <IconComponent {...rest} />;
};
