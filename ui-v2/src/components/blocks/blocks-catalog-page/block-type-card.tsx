import { Link } from "@tanstack/react-router";
import type { BlockType } from "@/api/block-types";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";

type BlockTypeCardProps = {
	blockType: BlockType;
};

export function BlockTypeCard({ blockType }: BlockTypeCardProps) {
	return (
		<Card className="p-6">
			<div className="flex items-center gap-4">
				<BlockTypeLogo size="lg" logoUrl={blockType.logo_url} />
				<h4 className="text-xl font-semibold tracking-tight">
					{blockType.name}
				</h4>
			</div>

			{blockType.description && (
				<div className="prose max-w-none h-32 overflow-y-auto text-sm">
					<LazyMarkdown>{blockType.description}</LazyMarkdown>
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
