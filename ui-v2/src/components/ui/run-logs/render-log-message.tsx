import { createElement, Fragment, type ReactNode } from "react";
import { linkify } from "@/lib/linkify";

/**
 * Maps ANSI SGR (Select Graphic Rendition) parameter codes to Tailwind classes.
 * Mirrors the mapping used by the legacy Vue UI so both surfaces render
 * colorized log output (`rich`, `colorama`, captured subprocess output, etc.)
 * consistently.
 */
const ANSI_SGR_TO_CLASS: Record<string, string> = {
	// Foreground colors
	"30": "text-black dark:text-black",
	"31": "text-red-600 dark:text-red-500",
	"32": "text-green-600 dark:text-green-500",
	"33": "text-yellow-600 dark:text-yellow-500",
	"34": "text-blue-600 dark:text-blue-500",
	"35": "text-purple-600 dark:text-purple-500",
	"36": "text-cyan-600 dark:text-cyan-500",
	"37": "text-gray-50 dark:text-gray-100",

	// Bright foreground colors
	"90": "text-gray-500 dark:text-gray-300",
	"91": "text-red-500 dark:text-red-300",
	"92": "text-green-500 dark:text-green-300",
	"93": "text-yellow-500 dark:text-yellow-300",
	"94": "text-blue-500 dark:text-blue-300",
	"95": "text-purple-500 dark:text-purple-300",
	"96": "text-cyan-500 dark:text-cyan-300",
	"97": "text-white",

	// Background colors
	"40": "bg-black",
	"41": "bg-red-500",
	"42": "bg-green-500",
	"43": "bg-yellow-500",
	"44": "bg-blue-500",
	"45": "bg-purple-500",
	"46": "bg-cyan-500",
	"47": "bg-gray-100",

	// Bright background colors
	"100": "bg-gray-300",
	"101": "bg-red-300",
	"102": "bg-green-300",
	"103": "bg-yellow-300",
	"104": "bg-blue-300",
	"105": "bg-purple-300",
	"106": "bg-cyan-300",
	"107": "bg-white",

	// Text styling
	"1": "font-bold",
	"2": "opacity-75",
	"3": "italic",
	"4": "underline",
	"9": "line-through",

	// Reset
	"0": "",
};

// Matches an ANSI SGR escape sequence (e.g. ESC[32m or ESC[1;38;5;196m) and
// captures its semicolon-separated parameter list. Built from a computed escape
// character to avoid embedding a control character in the source.
const ANSI_SGR_REGEX = new RegExp(
	`${String.fromCharCode(27)}\\[([\\d;]*)m`,
	"g",
);

// SGR codes that introduce an extended color and consume trailing parameters:
// `<code>;5;<n>` (256-color) or `<code>;2;<r>;<g>;<b>` (truecolor). We have no
// Tailwind equivalent for these, so they are consumed and stripped rather than
// misinterpreted as separate styling codes.
const EXTENDED_COLOR_CODES = new Set(["38", "48", "58"]);

/**
 * Applies a single SGR parameter list to the current set of active classes,
 * returning the updated set.
 */
function applySgrParams(params: string[], activeClasses: string[]): string[] {
	let next = activeClasses;

	for (let i = 0; i < params.length; i++) {
		const code = params[i];

		if (EXTENDED_COLOR_CODES.has(code)) {
			const mode = params[i + 1];
			if (mode === "5") {
				i += 2;
			} else if (mode === "2") {
				i += 4;
			}
			continue;
		}

		const newClass = ANSI_SGR_TO_CLASS[code];

		if (newClass === "") {
			next = [];
		} else if (newClass && !next.includes(newClass)) {
			next = [...next, newClass];
		}
	}

	return next;
}

/**
 * Renders a log message as React nodes, translating ANSI SGR escape codes into
 * styled spans and linkifying any URLs within the resulting text. Unrecognized
 * escape sequences are stripped so they never appear literally in the output.
 */
export function renderLogMessage(message: string): ReactNode {
	const children: ReactNode[] = [];
	let activeClasses: string[] = [];
	let lastIndex = 0;
	let key = 0;

	const pushSegment = (text: string) => {
		if (text.length === 0) {
			return;
		}

		const className = activeClasses.join(" ") || undefined;
		children.push(
			createElement(
				Fragment,
				{ key: `segment-${key++}` },
				linkify(text, className),
			),
		);
	};

	for (const match of message.matchAll(ANSI_SGR_REGEX)) {
		const index = match.index ?? 0;

		if (index > lastIndex) {
			pushSegment(message.slice(lastIndex, index));
		}

		const [fullMatch, code] = match;
		// An empty parameter list (ESC[m) is equivalent to a reset (ESC[0m).
		const params = code === "" ? ["0"] : code.split(";");
		activeClasses = applySgrParams(params, activeClasses);

		lastIndex = index + fullMatch.length;
	}

	if (lastIndex < message.length) {
		pushSegment(message.slice(lastIndex));
	}

	return createElement(Fragment, null, ...children);
}
