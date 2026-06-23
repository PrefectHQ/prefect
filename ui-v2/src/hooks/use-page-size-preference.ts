import { useEffect, useRef } from "react";
import { useLocalStorage } from "./use-local-storage";

const STORAGE_KEY = "prefect-page-size";
const DEFAULT_PAGE_SIZE = 10;

/**
 * Persists a page size preference in localStorage and syncs it with URL state.
 *
 * On first mount, if `urlPageSize` is `undefined` (no explicit limit in the URL),
 * the stored preference is written into the URL via `onInitialize`. When the user
 * changes the page size (reflected by a new `urlPageSize`), the value is saved to
 * localStorage for future visits.
 *
 * @param urlPageSize - Current page size from URL search params, or `undefined` if not set
 * @param onInitialize - Callback to set the page size in the URL when restoring from storage
 * @returns The effective page size to use (URL value if present, otherwise stored preference)
 */
export function usePageSizePreference(
	urlPageSize: number | undefined,
	onInitialize: (pageSize: number) => void,
): number {
	const [storedPageSize, setStoredPageSize] = useLocalStorage<number>(
		STORAGE_KEY,
		DEFAULT_PAGE_SIZE,
	);

	const hasInitializedRef = useRef(false);

	useEffect(() => {
		if (hasInitializedRef.current) return;
		hasInitializedRef.current = true;
		if (urlPageSize === undefined) {
			onInitialize(storedPageSize);
		}
	}, [urlPageSize, storedPageSize, onInitialize]);

	useEffect(() => {
		if (urlPageSize !== undefined && urlPageSize !== storedPageSize) {
			setStoredPageSize(urlPageSize);
		}
	}, [urlPageSize, storedPageSize, setStoredPageSize]);

	return urlPageSize ?? storedPageSize;
}
