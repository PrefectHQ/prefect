import { createElement, Fragment, type ReactNode } from "react";

const URL_REGEX = /(https?:\/\/[^\s/$.?#].[^\s)"('[{<>}]*)/g;

export function linkify(text: string): ReactNode {
	const children: ReactNode[] = [];
	let lastIndex = 0;

	for (const match of text.matchAll(URL_REGEX)) {
		const [url] = match;
		const index = match.index ?? 0;

		if (index > lastIndex) {
			children.push(
				createElement(
					"span",
					{ key: `text-${lastIndex}` },
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
					className:
						"text-link hover:text-link-hover hover:underline break-all",
				},
				href,
			),
		);

		if (tail.length > 0) {
			children.push(createElement("span", { key: `tail-${index}` }, tail));
		}

		lastIndex = index + url.length;
	}

	if (lastIndex < text.length) {
		children.push(
			createElement(
				"span",
				{ key: `text-${lastIndex}` },
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
