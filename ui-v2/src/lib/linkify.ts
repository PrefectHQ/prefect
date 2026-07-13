import { createElement, Fragment, type ReactNode } from "react";

const URL_REGEX = /(https?:\/\/[^\s/$.?#].[^\s)"(]*)/g;

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

		children.push(
			createElement(
				"a",
				{
					key: `link-${index}`,
					href: url,
					target: "_blank",
					rel: "noopener noreferrer",
					className:
						"text-link hover:text-link-hover hover:underline break-all",
				},
				url,
			),
		);

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
