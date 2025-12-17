import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog/delete-confirmation-dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

export type SavedFilter = {
	id: string | null;
	name: string;
	isDefault: boolean;
};

export type SavedFiltersMenuPermissions = {
	canSave: boolean;
	canDelete: boolean;
};

export type SavedFiltersMenuProps = {
	currentFilter: SavedFilter | null;
	savedFilters: SavedFilter[];
	onSelect: (filter: SavedFilter) => void;
	onSave: () => void;
	onDelete: (id: string) => void;
	onSetDefault: (id: string) => void;
	onRemoveDefault: (id: string) => void;
	permissions?: SavedFiltersMenuPermissions;
};

const CUSTOM_FILTER_NAME = "Custom";
const UNSAVED_FILTER_NAME = "Unsaved";

function isCustomOrUnsavedFilter(filter: SavedFilter | null): boolean {
	if (!filter) return true;
	return (
		filter.name === CUSTOM_FILTER_NAME || filter.name === UNSAVED_FILTER_NAME
	);
}

export const SavedFiltersMenu = ({
	currentFilter,
	savedFilters,
	onSelect,
	onSave,
	onDelete,
	onSetDefault,
	onRemoveDefault,
	permissions = { canSave: true, canDelete: true },
}: SavedFiltersMenuProps) => {
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);

	const displayName = currentFilter?.name ?? CUSTOM_FILTER_NAME;
	const isCustomUnsaved = isCustomOrUnsavedFilter(currentFilter);
	const canSave = isCustomUnsaved && permissions.canSave;
	const canDelete = currentFilter?.id && permissions.canDelete;
	const canToggleDefault = !isCustomUnsaved;

	const handleDelete = () => {
		if (!currentFilter?.id) return;
		onDelete(currentFilter.id);
		setShowDeleteDialog(false);
	};

	const handleToggleDefault = () => {
		if (!currentFilter?.id) return;
		if (currentFilter.isDefault) {
			onRemoveDefault(currentFilter.id);
		} else {
			onSetDefault(currentFilter.id);
		}
	};

	return (
		<>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="outline" className="gap-2">
						<Icon id="SlidersVertical" className="size-4" />
						<span>{displayName}</span>
						<Icon id="ChevronDown" className="size-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="start" className="min-w-[200px]">
					{savedFilters.map((filter) => (
						<DropdownMenuItem
							key={filter.id ?? filter.name}
							onClick={() => onSelect(filter)}
							className="flex items-center justify-between"
						>
							<span>{filter.name}</span>
							{filter.isDefault && (
								<Icon id="CircleCheck" className="size-4 text-green-500" />
							)}
						</DropdownMenuItem>
					))}

					{(canSave || canDelete || canToggleDefault) && (
						<DropdownMenuSeparator />
					)}

					{canSave && (
						<DropdownMenuItem onClick={onSave}>
							<Icon id="Plus" className="mr-2 size-4" />
							Save current filters
						</DropdownMenuItem>
					)}

					{canDelete && (
						<DropdownMenuItem
							variant="destructive"
							onClick={() => setShowDeleteDialog(true)}
						>
							<Icon id="Trash2" className="mr-2 size-4" />
							Delete
						</DropdownMenuItem>
					)}

					{canToggleDefault && (
						<DropdownMenuItem onClick={handleToggleDefault}>
							<Icon id="CircleCheck" className="mr-2 size-4" />
							{currentFilter?.isDefault
								? "Remove as default"
								: "Set as default"}
						</DropdownMenuItem>
					)}
				</DropdownMenuContent>
			</DropdownMenu>

			<DeleteConfirmationDialog
				isOpen={showDeleteDialog}
				title="Delete saved filter"
				description={`Are you sure you want to delete "${currentFilter?.name}"? This action cannot be undone.`}
				onConfirm={handleDelete}
				onClose={() => setShowDeleteDialog(false)}
			/>
		</>
	);
};
