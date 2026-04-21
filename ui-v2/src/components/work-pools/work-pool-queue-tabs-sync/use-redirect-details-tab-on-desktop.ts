import { useEffect } from "react";

/**
 * Keeps the work pool queue tab URL in sync with the viewport.
 *
 * The "Details" tab trigger is only rendered on narrow viewports
 * (`xl:hidden`) since its content is also shown in the sidebar well on
 * wider viewports. If the URL lands on "Details" while the sidebar is
 * visible, redirect to the default "Upcoming Runs" tab to avoid
 * duplicating content and to mirror the V1 behavior where `useTabs`
 * auto-selected the first visible tab.
 *
 * Reads `--breakpoint-xl` from the document so the threshold stays in
 * sync with Tailwind's theme instead of hardcoding a pixel value.
 */
export function useRedirectDetailsTabOnDesktop(
	queueTab: string,
	redirect: () => void,
) {
	useEffect(() => {
		if (queueTab !== "Details") {
			return;
		}

		const bp = getComputedStyle(document.documentElement)
			.getPropertyValue("--breakpoint-xl")
			.trim();
		if (!bp) {
			return;
		}

		const mql = window.matchMedia(`(min-width: ${bp})`);
		const syncTab = () => {
			if (mql.matches) {
				redirect();
			}
		};
		syncTab();
		mql.addEventListener("change", syncTab);
		return () => mql.removeEventListener("change", syncTab);
	}, [queueTab, redirect]);
}
