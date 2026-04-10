import { useCallback } from "react";
import { useLocalStorage } from "@/hooks/use-local-storage";

const DRAFT_KEY_PREFIX = "prefect-ui-v2-block-create-draft";

type BlockCreateDraft = {
	blockName: string;
	values: Record<string, unknown>;
};

const EMPTY_DRAFT: BlockCreateDraft = {
	blockName: "",
	values: {},
};

function getDraftKey(blockTypeSlug: string): string {
	return `${DRAFT_KEY_PREFIX}-${blockTypeSlug}`;
}

type UseBlockCreateDraftReturn = {
	draft: BlockCreateDraft;
	updateDraft: (partial: Partial<BlockCreateDraft>) => void;
	clearDraft: () => void;
};

/**
 * Hook to persist block create form draft values in localStorage.
 *
 * Draft is keyed by block type slug so each block type has its own draft.
 * Call `clearDraft()` on successful save to remove stale data.
 *
 * @param blockTypeSlug - The slug of the block type being created
 */
export function useBlockCreateDraft(
	blockTypeSlug: string,
): UseBlockCreateDraftReturn {
	const key = getDraftKey(blockTypeSlug);
	const [draft, setDraft] = useLocalStorage<BlockCreateDraft>(key, EMPTY_DRAFT);

	const updateDraft = useCallback(
		(partial: Partial<BlockCreateDraft>) => {
			setDraft((prev) => ({ ...prev, ...partial }));
		},
		[setDraft],
	);

	const clearDraft = useCallback(() => {
		setDraft(EMPTY_DRAFT);
		localStorage.removeItem(key);
	}, [setDraft, key]);

	return { draft, updateDraft, clearDraft };
}
