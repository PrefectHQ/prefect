import { useEffect } from "react";

/**
 * Redirects the tab search param from "Details" to a fallback (e.g. "Runs")
 * while the viewport is at or above the `lg` Tailwind breakpoint, where the
 * details sidebar is visible and the Details tab is hidden via `lg:hidden`.
 *
 * Reads `--breakpoint-lg` from the document root so the threshold stays in
 * sync with Tailwind's theme instead of hardcoding a pixel value.
 *
 * Mirrors the V1 behavior where `useTabs` auto-selected the first visible tab
 * (see `ui/src/pages/WorkPool.vue` and legacy `prefect-ui-library` useTabs).
 */
export function useRedirectDetailsTabOnDesktop({
	tab,
	fallbackTab,
	navigate,
}: {
	tab: string;
	fallbackTab: string;
	navigate: (tab: string) => void;
}) {
	useEffect(() => {
		if (tab !== "Details") {
			return;
		}

		const bp = getComputedStyle(document.documentElement)
			.getPropertyValue("--breakpoint-lg")
			.trim();
		if (!bp) {
			return;
		}

		const mql = window.matchMedia(`(min-width: ${bp})`);
		const syncTab = () => {
			if (mql.matches) {
				navigate(fallbackTab);
			}
		};
		syncTab();
		mql.addEventListener("change", syncTab);
		return () => mql.removeEventListener("change", syncTab);
	}, [tab, fallbackTab, navigate]);
}
