import { Link } from "@tanstack/react-router";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BlockType } from "@/api/block-types";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { PythonBlockSnippet } from "@/components/blocks/python-example-snippet";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

type BlockTypePageProps = {
	blockType: BlockType;
};

export const BlockTypePage = ({ blockType }: BlockTypePageProps) => {
	return (
		<div className="flex flex-col gap-6">
			<BlockTypePageHeader blockType={blockType} />
			<BlockTypeCardDetails blockType={blockType} />
		</div>
	);
};

function BlockTypePageHeader({ blockType }: BlockTypePageProps) {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/blocks" className="text-xl font-semibold">
						Blocks
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem>
					<BreadcrumbLink
						to="/blocks/catalog"
						className="text-xl font-semibold"
					>
						Catalog
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem className="text-xl font-semibold">
					{blockType.slug}
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
}

function BlockTypeCardDetails({ blockType }: BlockTypePageProps) {
	return (
		<div>
			<Card className="p-6">
				<div className="flex items-center gap-4">
					<BlockTypeLogo size="lg" logoUrl={blockType.logo_url} />
					<Typography variant="h3">{blockType.name}</Typography>
				</div>

				{blockType.description && (
					<BlockTypeDescription
						description={blockType.description}
						documentationUrl={blockType.documentation_url}
					/>
				)}

				{blockType.code_example && (
					<div className="flex flex-col gap-4">
						<Typography variant="h4">Example</Typography>
						<PythonBlockSnippet
							codeExample={blockType.code_example}
							name={blockType.name}
						/>
					</div>
				)}

				<div className="flex justify-end">
					<Button>
						<Link
							to="/blocks/catalog/$slug/create"
							params={{ slug: blockType.slug }}
						>
							Create
						</Link>
					</Button>
				</div>
			</Card>
		</div>
	);
}

type BlockTypeDescriptionProps = {
	description: string;
	documentationUrl: string | null | undefined;
};
function BlockTypeDescription({
	description,
	documentationUrl,
}: BlockTypeDescriptionProps) {
	let retDescription = description;
	if (documentationUrl) {
		retDescription = `${retDescription} [Documentation](${documentationUrl})`;
	}

	return (
		<div className="prose max-w-none">
			<Markdown remarkPlugins={[remarkGfm]}>{retDescription}</Markdown>
		</div>
	);
}
