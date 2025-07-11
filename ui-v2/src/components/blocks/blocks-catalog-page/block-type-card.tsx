import { Link } from "@tanstack/react-router";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BlockType } from "@/api/block-types";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

type BlockTypeCardProps = {
	blockType: BlockType;
};

export function BlockTypeCard({ blockType }: BlockTypeCardProps) {
	return (
		<Card className="p-6">
			<div className="flex items-center gap-4">
				<BlockTypeLogo size="lg" logoUrl={blockType.logo_url} />
				<Typography variant="h4">{blockType.name}</Typography>
			</div>

			{blockType.description && (
				<div className="prose max-w-none h-32 overflow-y-scroll text-sm">
					<Markdown remarkPlugins={[remarkGfm]}>
						{blockType.description}
					</Markdown>
				</div>
			)}

			<div className="flex justify-end gap-4">
				<Button variant="secondary" size="sm">
					<Link to="/blocks/catalog/$slug" params={{ slug: blockType.slug }}>
						Details
					</Link>
				</Button>

				<Button size="sm">
					<Link
						to="/blocks/catalog/$slug/create"
						params={{ slug: blockType.slug }}
					>
						Create
					</Link>
				</Button>
			</div>
		</Card>
	);
}
