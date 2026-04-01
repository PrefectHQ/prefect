type RichArtifactData = {
	html: string;
	sandbox: string[];
	csp?: string;
};

export type DetailRichProps = {
	richData: unknown;
};

const isRichArtifactData = (value: unknown): value is RichArtifactData => {
	if (typeof value !== "object" || value === null) {
		return false;
	}

	const candidate = value as Partial<RichArtifactData>;
	return (
		typeof candidate.html === "string" &&
		Array.isArray(candidate.sandbox) &&
		candidate.sandbox.every((token) => typeof token === "string") &&
		(candidate.csp === undefined || typeof candidate.csp === "string")
	);
};

const injectCsp = (html: string, csp: string): string => {
	const cspTag = `<meta http-equiv="Content-Security-Policy" content="${csp}">`;
	const hasHeadTag = /<head\b[^>]*>/i.test(html);

	if (hasHeadTag) {
		return html.replace(/<head\b[^>]*>/i, (match) => `${match}${cspTag}`);
	}

	return `<!doctype html><html><head>${cspTag}</head><body>${html}</body></html>`;
};

export const DetailRich = ({ richData }: DetailRichProps) => {
	if (!isRichArtifactData(richData)) {
		return (
			<div
				data-testid="rich-display-invalid"
				className="rounded-md border border-border p-4 text-sm text-muted-foreground"
			>
				Invalid rich artifact payload.
			</div>
		);
	}

	const srcDoc = richData.csp
		? injectCsp(richData.html, richData.csp)
		: richData.html;

	// Strip allow-same-origin when allow-scripts is present to prevent sandbox
	// escape (same-origin + scripts lets embedded JS access the parent page).
	const sanitizedSandbox = richData.sandbox.filter((token) => {
		const normalized = token.toLowerCase().trim();
		if (normalized !== "allow-same-origin") return true;
		return !richData.sandbox.some(
			(t) => t.toLowerCase().trim() === "allow-scripts",
		);
	});

	return (
		<div data-testid="rich-display" className="mt-2">
			<iframe
				data-testid="rich-artifact-iframe"
				title="rich-artifact-preview"
				className="w-full min-h-[28rem] rounded-md border border-border bg-background"
				sandbox={sanitizedSandbox.join(" ")}
				srcDoc={srcDoc}
			/>
		</div>
	);
};
