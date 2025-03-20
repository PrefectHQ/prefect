import { BlockDocument } from "@/api/block-documents";
import { Typography } from "@/components/ui/typography";
import { Link } from "@tanstack/react-router";

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
				<div className="p-1 bg-gray-300 rounded-md">
					<img
						alt={`${block_type_name} logo`}
						src={block_type.logo_url ?? undefined}
						className="size-6"
					/>
				</div>
			)}
			<div className="flex flex-col">
				{name && (
					<Link to="/blocks/block/$id" params={{ id }}>
						<Typography className="font-semibold">{name}</Typography>
					</Link>
				)}
				{block_type_name && blockDocument.block_type?.slug && (
					<Link
						to="/blocks/catalog/$slug"
						params={{ slug: blockDocument.block_type.slug }}
					>
						<Typography variant="bodySmall" className="text-muted-foreground">
							{block_type_name}
						</Typography>
					</Link>
				)}
			</div>
		</div>
	);
};
