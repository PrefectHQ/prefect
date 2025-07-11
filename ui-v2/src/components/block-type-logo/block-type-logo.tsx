import { cva } from "class-variance-authority";
import type { BlockType } from "@/api/block-types";

type BlockTypeLogoProps = {
	alt?: string;
	logoUrl: BlockType["logo_url"];
	size?: "sm" | "lg";
};

export const BlockTypeLogo = ({
	alt,
	logoUrl,
	size = "sm",
}: BlockTypeLogoProps) => (
	<img
		alt={alt}
		src={logoUrl ?? undefined}
		className={blockTypeLogoVariant({ size })}
	/>
);

const blockTypeLogoVariant = cva("border-4 bg-gray-200 rounded", {
	variants: {
		size: {
			sm: "size-8",
			lg: "size-14",
		},
	},
});
