import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BlockType } from "@/api/block-types";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

type BlockTypeDetailsProps = {
	blockType: BlockType;
};

export function BlockTypeDetails({ blockType }: BlockTypeDetailsProps) {
	return (
		<Card className="p-6 max-h-60">
			<div className="flex items-center gap-4">
				<BlockTypeLogo size="lg" logoUrl={blockType.logo_url} />
				<Typography variant="h4">{blockType.name}</Typography>
			</div>

			{blockType.description && (
				<div className="prose max-w-none overflow-y-scroll text-sm">
					<Markdown remarkPlugins={[remarkGfm]}>
						{blockType.description}
					</Markdown>
				</div>
			)}
		</Card>
	);
}
