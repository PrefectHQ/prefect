import type { MermaidConfig } from "mermaid";
import { useTheme } from "next-themes";
import { useEffect, useId, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";

type MermaidDiagramProps = {
	source: string;
};

type MermaidModule = typeof import("mermaid")["default"];

const cssVar = (name: string): string => {
	if (typeof document === "undefined") {
		return "";
	}
	return getComputedStyle(document.documentElement)
		.getPropertyValue(name)
		.trim();
};

const getMermaidConfig = (theme: "dark" | "light"): MermaidConfig => ({
	startOnLoad: false,
	securityLevel: "strict",
	theme: "base",
	flowchart: { useMaxWidth: true, padding: 16, curve: "basis" },
	sequence: { useMaxWidth: true },
	themeVariables: {
		primaryColor: cssVar("--muted"),
		primaryTextColor: cssVar("--foreground"),
		primaryBorderColor: cssVar("--border"),
		lineColor: cssVar("--border"),
		background: cssVar("--background"),
		mainBkg: cssVar("--card"),
		secondBkg: cssVar("--muted"),
		tertiaryColor: cssVar("--accent"),
		nodeBorder: cssVar("--border"),
		clusterBkg: cssVar("--card"),
		clusterBorder: cssVar("--border"),
		fontSize: "14px",
		darkMode: theme === "dark",
	},
});

export function MermaidDiagram({ source }: MermaidDiagramProps) {
	const { resolvedTheme } = useTheme();
	const [state, setState] = useState<"loading" | "success" | "error">(
		"loading",
	);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);
	const containerRef = useRef<HTMLDivElement | null>(null);
	const reactId = useId();
	// Mermaid requires DOM-id-safe identifiers (no colons).
	const diagramId = `mermaid-${reactId.replace(/:/g, "-")}`;

	useEffect(() => {
		let cancelled = false;
		setState("loading");
		setErrorMessage(null);

		void import("mermaid").then(
			async ({ default: mermaid }: { default: MermaidModule }) => {
				if (cancelled) return;
				try {
					mermaid.initialize(
						getMermaidConfig(resolvedTheme === "dark" ? "dark" : "light"),
					);
					const { svg } = await mermaid.render(diagramId, source);
					if (cancelled || !containerRef.current) return;
					containerRef.current.innerHTML = svg;
					setState("success");
				} catch (err) {
					if (cancelled) return;
					setErrorMessage(err instanceof Error ? err.message : String(err));
					setState("error");
				}
			},
		);

		return () => {
			cancelled = true;
		};
	}, [source, resolvedTheme, diagramId]);

	if (state === "error") {
		return (
			<div className="rounded border border-destructive/40 bg-destructive/5 p-4 text-sm">
				<p className="mb-2 font-semibold text-destructive">
					Failed to render mermaid diagram
				</p>
				{errorMessage && (
					<details className="mb-2">
						<summary className="cursor-pointer text-destructive">
							Details
						</summary>
						<pre className="mt-1 overflow-auto rounded bg-background p-2 text-xs">
							{errorMessage}
						</pre>
					</details>
				)}
				<details>
					<summary className="cursor-pointer text-muted-foreground">
						Source
					</summary>
					<pre className="mt-1 overflow-auto rounded bg-background p-2 text-xs">
						{source}
					</pre>
				</details>
			</div>
		);
	}

	return (
		<div className="my-2">
			{state === "loading" && <Skeleton className="min-h-[120px] w-full" />}
			<div
				ref={containerRef}
				className={`flex w-full items-center justify-center overflow-auto [&>svg]:max-w-full ${
					state === "success" ? "" : "hidden"
				}`}
			/>
		</div>
	);
}
