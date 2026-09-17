import { useCallback, useSyncExternalStore } from "react";
import { z } from "zod";

export const PINNED_DEPLOYMENTS_STORAGE_KEY = "prefect-pinned-deployments";

const pinnedDeploymentIdsSchema = z.array(z.string());

const NO_PINNED_DEPLOYMENT_IDS: readonly string[] = [];

const listeners = new Set<() => void>();

let cachedRawValue: string | null = null;
let cachedPinnedDeploymentIds = NO_PINNED_DEPLOYMENT_IDS;

const readRawValue = () => {
	try {
		return localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY);
	} catch {
		return null;
	}
};

const parsePinnedDeploymentIds = (rawValue: string | null) => {
	if (!rawValue) return NO_PINNED_DEPLOYMENT_IDS;
	try {
		const result = pinnedDeploymentIdsSchema.safeParse(JSON.parse(rawValue));
		return result.success ? result.data : NO_PINNED_DEPLOYMENT_IDS;
	} catch {
		return NO_PINNED_DEPLOYMENT_IDS;
	}
};

/**
 * Reads the pinned deployment ids outside of React, e.g. in a route loader.
 */
export const getPinnedDeploymentIds = () => {
	const rawValue = readRawValue();
	if (rawValue !== cachedRawValue) {
		cachedRawValue = rawValue;
		cachedPinnedDeploymentIds = parsePinnedDeploymentIds(rawValue);
	}
	return cachedPinnedDeploymentIds;
};

const getServerSnapshot = () => NO_PINNED_DEPLOYMENT_IDS;

const subscribe = (listener: () => void) => {
	const onStorage = (event: StorageEvent) => {
		if (event.key === null || event.key === PINNED_DEPLOYMENTS_STORAGE_KEY) {
			listener();
		}
	};
	listeners.add(listener);
	window.addEventListener("storage", onStorage);
	return () => {
		listeners.delete(listener);
		window.removeEventListener("storage", onStorage);
	};
};

const writePinnedDeploymentIds = (pinnedDeploymentIds: readonly string[]) => {
	try {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(pinnedDeploymentIds),
		);
	} catch (error) {
		console.error("Failed to save pinned deployments", error);
		return;
	}
	for (const listener of listeners) {
		listener();
	}
};

/**
 * Pins deployments for the current browser. Pins are stored in localStorage
 * rather than on the server, so they are not shared between browsers or users.
 * Every component using this hook sees the same pins, including across tabs.
 *
 * @example
 * ```tsx
 * const { isPinned, togglePin } = usePinnedDeployments();
 * <button onClick={() => togglePin(deployment.id)}>
 *   {isPinned(deployment.id) ? "Unpin" : "Pin"}
 * </button>
 * ```
 */
export function usePinnedDeployments() {
	const pinnedDeploymentIds = useSyncExternalStore(
		subscribe,
		getPinnedDeploymentIds,
		getServerSnapshot,
	);

	const isPinned = useCallback(
		(deploymentId: string) => pinnedDeploymentIds.includes(deploymentId),
		[pinnedDeploymentIds],
	);

	const togglePin = useCallback((deploymentId: string) => {
		const current = getPinnedDeploymentIds();
		writePinnedDeploymentIds(
			current.includes(deploymentId)
				? current.filter((id) => id !== deploymentId)
				: [...current, deploymentId],
		);
	}, []);

	return { pinnedDeploymentIds, isPinned, togglePin };
}
