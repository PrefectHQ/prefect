import { createElement, Fragment, type ReactNode } from "react";

const URL_REGEX = /(https?:\/\/[^\s/$.?#].[^\s)"('[{<>}]*)/g;

/**
 * Converts URLs within a string of text into clickable anchor elements.
 *
 * @param text - The text to scan for URLs.
 * @param className - Optional class applied to the plain-text spans (and merged
 *   into the anchor styling), used by callers that need to carry styling — such
 *   as ANSI colors — through the linkified output.
 */
export function linkify(text: string, className?: string): ReactNode {
	const children: ReactNode[] = [];
	let lastIndex = 0;

	for (const match of text.matchAll(URL_REGEX)) {
		const [url] = match;
		const index = match.index ?? 0;

		if (index > lastIndex) {
			children.push(
				createElement(
					"span",
					{ key: `text-${lastIndex}`, className },
					text.slice(lastIndex, index),
				),
			);
		}

		const { href, tail } = trimTrailing(url);

		children.push(
			createElement(
				"a",
				{
					key: `link-${index}`,
					href,
					target: "_blank",
					rel: "noopener noreferrer",
					className: [
						"text-link hover:text-link-hover hover:underline break-all",
						className,
					]
						.filter(Boolean)
						.join(" "),
				},
				href,
			),
		);

		if (tail.length > 0) {
			children.push(
				createElement("span", { key: `tail-${index}`, className }, tail),
			);
		}

		lastIndex = index + url.length;
	}

	if (lastIndex < text.length) {
		children.push(
			createElement(
				"span",
				{ key: `text-${lastIndex}`, className },
				text.slice(lastIndex),
			),
		);
	}

	return createElement(Fragment, null, ...children);
}

const PUNCTUATION = /[.,;:!?]+/;

function trimTrailing(url: string): { href: string; tail: string } {
	let href = url;
	let tail = "";

	while (href.length > 0) {
		const last = href[href.length - 1];

		if (PUNCTUATION.test(last)) {
			tail = last + tail;
			href = href.slice(0, -1);
			continue;
		}

		if (last === "]" && !href.includes("[")) {
			tail = last + tail;
			href = href.slice(0, -1);
			continue;
		}

		break;
	}

	return { href, tail };
}
