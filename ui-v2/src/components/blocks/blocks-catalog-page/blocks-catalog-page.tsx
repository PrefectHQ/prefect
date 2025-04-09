import type { BlockType } from "@/api/block-types";
import { BlockTypesGrid } from "./block-types-grid";
import { BlocksCatalogMessage } from "./blocks-catalog-message";
import { BlocksCatalogPageHeader } from "./blocks-catalog-page-header";

type BlocksCatalogPageProps = {
	blockTypes: Array<BlockType>;
	search: string;
	onSearch: (value?: string) => void;
};

export const BlocksCatalogPage = ({
	blockTypes,
	search,
	onSearch,
}: BlocksCatalogPageProps) => {
	return (
		<div className="flex flex-col gap-6">
			<BlocksCatalogPageHeader />
			<BlocksCatalogMessage />
			<BlockTypesGrid
				blockTypes={blockTypes}
				search={search}
				onSearch={onSearch}
			/>
		</div>
	);
};
