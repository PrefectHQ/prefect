import { BlockDocument } from "@/api/block-documents";
import { SearchInput } from "@/components/ui/input";
import { RowSelectionState } from "@tanstack/react-table";
import { useState } from "react";
import { BlockDocumentsDataTable } from "./block-document-data-table";
import { BlocksPageHeader } from "./blocks-page-header";
import { BlocksRowCount } from "./blocks-row-count";
import { BlocksEmptyState } from "./empty-state";

type BlocksPageProps = {
	allCount: number;
	blockDocuments: Array<BlockDocument> | undefined;
	onSearch: (value?: string) => void;
	search: string;
};

export const BlocksPage = ({
	allCount,
	blockDocuments = [],
	onSearch,
	search,
}: BlocksPageProps) => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	return (
		<div className="flex flex-col gap-4">
			<BlocksPageHeader />
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
						<div>
							<SearchInput
								className="w-56"
								aria-label="search blocks"
								placeholder="Search blocks"
								value={search}
								onChange={(e) => onSearch(e.target.value)}
							/>
						</div>
					</div>
					<BlockDocumentsDataTable
						blockDocuments={blockDocuments}
						rowSelection={rowSelection}
						setRowSelection={setRowSelection}
						blockDocumentsCount={allCount}
						pageCount={0}
						pagination={{
							pageIndex: 0,
							pageSize: 10,
						}}
						onPaginationChange={() => {
							/** TODO */
						}}
					/>
				</div>
			)}
		</div>
	);
};
