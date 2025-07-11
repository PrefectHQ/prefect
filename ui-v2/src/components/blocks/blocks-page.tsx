import { Link } from "@tanstack/react-router";
import type { PaginationState, RowSelectionState } from "@tanstack/react-table";
import { useState } from "react";
import type { BlockDocument } from "@/api/block-documents";
import { Breadcrumb, BreadcrumbItem } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { SearchInput } from "@/components/ui/input";
import { BlockDocumentsDataTable } from "./block-document-data-table";
import { BlockTypesMultiSelect } from "./block-types-multi-select";
import { BlocksRowCount } from "./blocks-row-count";
import { BlocksEmptyState } from "./empty-state";

type BlocksPageProps = {
	allCount: number;
	blockDocuments: Array<BlockDocument> | undefined;
	onSearch: (value?: string) => void;
	search: string;
	blockTypeSlugsFilter: Array<string>;
	onToggleBlockTypeSlug: (blockTypeIds: string) => void;
	onRemoveBlockTypeSlug: (blockTypeIds: string) => void;
	pagination: PaginationState;
	onPaginationChange: (paginationState: PaginationState) => void;
};

export const BlocksPage = ({
	allCount,
	blockDocuments = [],
	onSearch,
	search,
	blockTypeSlugsFilter,
	onToggleBlockTypeSlug,
	onRemoveBlockTypeSlug,
	pagination,
	onPaginationChange,
}: BlocksPageProps) => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbItem className="text-xl font-semibold">
						Blocks
					</BreadcrumbItem>
				</Breadcrumb>
				<Button size="icon" className="size-7" variant="outline">
					<Link to="/blocks/catalog">
						<Icon id="Plus" className="size-4" />
					</Link>
				</Button>
			</div>
			{allCount === 0 ? (
				<BlocksEmptyState />
			) : (
				<div className="flex flex-col gap-4">
					<div className="flex items-center justify-between">
						<BlocksRowCount
							rowSelection={rowSelection}
							setRowSelection={setRowSelection}
							count={allCount}
						/>
						<div className="flex items-center gap-2">
							<BlockTypesMultiSelect
								selectedBlockTypesSlugs={blockTypeSlugsFilter}
								onToggleBlockTypeSlug={onToggleBlockTypeSlug}
								onRemoveBlockTypeSlug={onRemoveBlockTypeSlug}
							/>
							<div className="min-w-56">
								<SearchInput
									aria-label="search blocks"
									placeholder="Search blocks"
									value={search}
									onChange={(e) => onSearch(e.target.value)}
								/>
							</div>
						</div>
					</div>
					<BlockDocumentsDataTable
						blockDocuments={blockDocuments}
						rowSelection={rowSelection}
						setRowSelection={setRowSelection}
						blockDocumentsCount={allCount}
						pagination={pagination}
						onPaginationChange={onPaginationChange}
					/>
				</div>
			)}
		</div>
	);
};
