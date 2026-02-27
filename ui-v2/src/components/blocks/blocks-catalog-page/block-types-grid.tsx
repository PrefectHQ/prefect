import type { BlockType } from "@/api/block-types";
import { SearchInput } from "@/components/ui/input";
import { pluralize } from "@/utils";
import { BlockTypeCard } from "./block-type-card";

type BlockTypesGridProps = {
	blockTypes: Array<BlockType>;
	search: string;
	onSearch: (value?: string) => void;
};

export const BlockTypesGrid = ({
	blockTypes,
	search,
	onSearch,
}: BlockTypesGridProps) => {
	return (
		<div className="flex flex-col gap-4">
			<div className="flex justify-between items-center">
				<p className="text-sm text-muted-foreground">
					{blockTypes.length.toLocaleString()}{" "}
					{pluralize(blockTypes.length, "Block")}
				</p>
				<div className="min-w-40">
					<SearchInput
						value={search}
						placeholder="Search blocks"
						onChange={(e) => onSearch(e.target.value)}
					/>
				</div>
			</div>
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
				{blockTypes.map((blockType) => (
					<BlockTypeCard key={blockType.id} blockType={blockType} />
				))}
			</div>
		</div>
	);
};
