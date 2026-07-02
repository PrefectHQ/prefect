type RichArtifactData = {
	html: string;
	sandbox?: string[];
	csp?: string;
};

type NormalizedRichArtifactData = {
	html: string;
	sandbox: string[];
};

export type DetailRichProps = {
	richData: unknown;
};

const DEFAULT_RICH_SANDBOX = ["allow-scripts"];
const DEFAULT_RICH_CSP = (sandbox: string[]): string => {
	const hasAllowScripts = sandbox.includes("allow-scripts");
	const scriptSrc = hasAllowScripts ? "'unsafe-inline'" : "'none'";

	return [
		"default-src 'none'",
		`script-src ${scriptSrc}`,
		"style-src 'unsafe-inline'",
		"img-src data:",
		"font-src data:",
		"media-src data:",
		"connect-src 'none'",
		"base-uri 'none'",
		"form-action 'none'",
		"frame-src 'none'",
		"object-src 'none'",
		"worker-src 'none'",
		"manifest-src 'none'",
	].join("; ");
};

// Only forward explicitly reviewed tokens that keep content confined to the
// iframe. Navigation- and popup-capable permissions are intentionally omitted.
const SAFE_RICH_SANDBOX_TOKENS = new Set([
	"allow-same-origin",
	"allow-scripts",
]);

const sanitizeSandbox = (sandbox: string[]): string[] => {
	const normalizedTokens = sandbox.map((token) => token.toLowerCase().trim());
	const hasAllowScripts = normalizedTokens.includes("allow-scripts");
	const seen = new Set<string>();

	return normalizedTokens.filter((token) => {
		if (!SAFE_RICH_SANDBOX_TOKENS.has(token)) {
			return false;
		}

		// Same-origin + scripts lets embedded JS access the parent page.
		if (token === "allow-same-origin" && hasAllowScripts) {
			return false;
		}

		if (seen.has(token)) {
			return false;
		}

		seen.add(token);
		return true;
	});
};

const parseRichArtifactData = (
	value: unknown,
): NormalizedRichArtifactData | null => {
	if (typeof value !== "object" || value === null) {
		return null;
	}

	const candidate = value as Partial<RichArtifactData>;

	if (typeof candidate.html !== "string") {
		return null;
	}

	if (
		candidate.sandbox !== undefined &&
		(!Array.isArray(candidate.sandbox) ||
			!candidate.sandbox.every((token) => typeof token === "string"))
	) {
		return null;
	}

	const sanitizedSandbox = sanitizeSandbox(
		candidate.sandbox ?? DEFAULT_RICH_SANDBOX,
	);

	return {
		html: candidate.html,
		sandbox: sanitizedSandbox,
	};
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
	const parsedRichData = parseRichArtifactData(richData);

	if (!parsedRichData) {
		return (
			<div
				data-testid="rich-display-invalid"
				className="rounded-md border border-border p-4 text-sm text-muted-foreground"
			>
				Invalid rich artifact payload.
			</div>
		);
	}

	// Ignore any persisted CSP field and derive a fixed restrictive policy from
	// the sanitized sandbox permissions instead.
	const srcDoc = injectCsp(
		parsedRichData.html,
		DEFAULT_RICH_CSP(parsedRichData.sandbox),
	);

	return (
		<div data-testid="rich-display" className="mt-2">
			<iframe
				data-testid="rich-artifact-iframe"
				title="rich-artifact-preview"
				className="w-full min-h-[28rem] rounded-md border border-border bg-background"
				sandbox={parsedRichData.sandbox.join(" ")}
				srcDoc={srcDoc}
			/>
		</div>
	);
};
