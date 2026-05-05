import type { BlockType } from "@/api/block-types";
import { Button } from "@/components/ui/button";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { SearchInput } from "@/components/ui/input";
import { pluralize } from "@/utils";
import { BlockTypeCard } from "./block-type-card";

type BlockTypesGridProps = {
	blockTypes: Array<BlockType>;
	search: string;
	onSearch: (value?: string) => void;
	onClearFilters: () => void;
};

export const BlockTypesGrid = ({
	blockTypes,
	search,
	onSearch,
	onClearFilters,
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
			{blockTypes.length === 0 && search ? (
				<BlocksCatalogFilteredEmptyState onClearFilters={onClearFilters} />
			) : (
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
					{blockTypes.map((blockType) => (
						<BlockTypeCard key={blockType.id} blockType={blockType} />
					))}
				</div>
			)}
		</div>
	);
};

const BlocksCatalogFilteredEmptyState = ({
	onClearFilters,
}: {
	onClearFilters: () => void;
}) => (
	<EmptyState>
		<EmptyStateIcon id="Search" />
		<EmptyStateTitle>No block types match your search</EmptyStateTitle>
		<EmptyStateDescription>
			Try adjusting your search terms.
		</EmptyStateDescription>
		<EmptyStateActions>
			<Button variant="outline" onClick={onClearFilters}>
				Clear filters
			</Button>
		</EmptyStateActions>
	</EmptyState>
);
