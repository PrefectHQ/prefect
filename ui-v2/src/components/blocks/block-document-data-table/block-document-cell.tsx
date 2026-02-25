import { Link } from "@tanstack/react-router";
import type { BlockDocument } from "@/api/block-documents";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";

type BlockDocumentCellProps = {
	blockDocument: BlockDocument;
};

export const BlockDocumentCell = ({
	blockDocument,
}: BlockDocumentCellProps) => {
	const { id, name, block_type, block_type_name } = blockDocument;

	return (
		<div className="flex gap-4 items-center">
			{block_type && block_type_name && (
				<BlockTypeLogo
					size="sm"
					logoUrl={block_type.logo_url}
					alt={`${block_type_name} logo`}
				/>
			)}
			<div className="flex flex-col">
				{name && (
					<Link to="/blocks/block/$id" params={{ id }}>
						<p
							className="text-base font-semibold truncate max-w-xs"
							title={name}
						>
							{name}
						</p>
					</Link>
				)}
				{block_type_name && blockDocument.block_type?.slug && (
					<Link
						to="/blocks/catalog/$slug"
						params={{ slug: blockDocument.block_type.slug }}
					>
						<p className="text-sm text-muted-foreground">{block_type_name}</p>
					</Link>
				)}
			</div>
		</div>
	);
};
