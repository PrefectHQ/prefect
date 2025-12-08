import {
	CopyIcon,
	EllipsisVerticalIcon,
	SaveIcon,
	TrashIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SaveFilterModal } from "./save-filter-modal";
import type { SavedFlowRunsSearch } from "./saved-filters";
import { SavedFiltersDeleteDialog } from "./saved-filters-delete-dialog";
import {
	CUSTOM_FILTER_NAME,
	getDefaultSavedSearchFilter,
	isSameFilter,
	removeDefaultSavedSearchFilter,
	setDefaultSavedSearchFilter,
	UNSAVED_FILTER_NAME,
} from "./saved-filters-utils";

type SavedFiltersMenuProps = {
	savedSearch: SavedFlowRunsSearch;
	onSaved?: (savedSearch: SavedFlowRunsSearch) => void;
	onDeleted?: () => void;
};

export function SavedFiltersMenu({
	savedSearch,
	onSaved,
	onDeleted,
}: SavedFiltersMenuProps) {
	const [showSaveModal, setShowSaveModal] = useState(false);
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);

	const isCustomUnsavedFilter =
		savedSearch.name === CUSTOM_FILTER_NAME ||
		savedSearch.name === UNSAVED_FILTER_NAME;

	const canSave = isCustomUnsavedFilter;
	const canDelete = savedSearch.id !== null;

	const defaultFilter = getDefaultSavedSearchFilter();
	const isCurrentDefault = isSameFilter(savedSearch.filters, defaultFilter);

	const canToggleDefault = !isCustomUnsavedFilter;

	const handleShareView = async () => {
		try {
			await navigator.clipboard.writeText(window.location.href);
			toast.success("Link copied to clipboard");
		} catch {
			toast.error("Failed to copy link");
		}
	};

	const handleToggleDefault = () => {
		if (isCurrentDefault) {
			removeDefaultSavedSearchFilter();
			toast.success("Default filter removed");
		} else {
			setDefaultSavedSearchFilter(savedSearch.filters);
			toast.success("Default filter set");
		}
	};

	const handleSaved = (newSavedSearch: SavedFlowRunsSearch) => {
		setShowSaveModal(false);
		onSaved?.(newSavedSearch);
	};

	const handleDeleted = () => {
		setShowDeleteDialog(false);
		onDeleted?.();
	};

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" size="icon">
						<EllipsisVerticalIcon className="h-4 w-4" />
						<span className="sr-only">Open menu</span>
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuItem onClick={() => void handleShareView()}>
						<CopyIcon className="mr-2 h-4 w-4" />
						Share View
					</DropdownMenuItem>
					{canSave && (
						<DropdownMenuItem onClick={() => setShowSaveModal(true)}>
							<SaveIcon className="mr-2 h-4 w-4" />
							Save View
						</DropdownMenuItem>
					)}
					{canDelete && (
						<DropdownMenuItem
							onClick={() => setShowDeleteDialog(true)}
							className="text-destructive focus:text-destructive"
						>
							<TrashIcon className="mr-2 h-4 w-4" />
							Delete View
						</DropdownMenuItem>
					)}
					{canToggleDefault && (
						<DropdownMenuItem onClick={handleToggleDefault}>
							{isCurrentDefault ? "Remove as default" : "Set as default"}
						</DropdownMenuItem>
					)}
				</DropdownMenuContent>
			</DropdownMenu>

			<SaveFilterModal
				open={showSaveModal}
				onOpenChange={setShowSaveModal}
				savedSearch={savedSearch}
				onSaved={handleSaved}
			/>

			{savedSearch.id && (
				<SavedFiltersDeleteDialog
					open={showDeleteDialog}
					onOpenChange={setShowDeleteDialog}
					savedSearch={savedSearch}
					onDeleted={handleDeleted}
				/>
			)}
		</>
	);
}
