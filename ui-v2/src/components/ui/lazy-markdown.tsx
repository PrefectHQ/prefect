import { useEffect, useMemo, useState } from "react";
import type { Components, Options, UrlTransform } from "react-markdown";
import { MermaidDiagram } from "@/components/ui/mermaid-diagram";
import { Skeleton } from "@/components/ui/skeleton";

type Pluggable = NonNullable<Options["rehypePlugins"]>[number];

type LazyMarkdownProps = Omit<Options, "children"> & {
	children: string;
};

type MarkdownModules = {
	Markdown: React.ComponentType<Options>;
	urlTransform: UrlTransform;
	remarkPlugins: Pluggable[];
	rehypePlugins: Pluggable[];
};

const IMAGE_DATA_URL = /^data:image\//;

function buildUrlTransform(defaultUrlTransform: UrlTransform): UrlTransform {
	return (url, key, node) =>
		node.tagName === "img" && key === "src" && IMAGE_DATA_URL.test(url)
			? url
			: defaultUrlTransform(url, key, node);
}

function reactNodeToString(node: React.ReactNode): string {
	if (node == null || typeof node === "boolean") return "";
	if (typeof node === "string") return node;
	if (typeof node === "number") return String(node);
	if (Array.isArray(node)) return node.map(reactNodeToString).join("");
	return "";
}

const mermaidComponents: Components = {
	code({ className, children, ...props }) {
		if (
			typeof className === "string" &&
			className.includes("language-mermaid")
		) {
			return (
				<MermaidDiagram
					source={reactNodeToString(children).replace(/\n$/, "")}
				/>
			);
		}
		return (
			<code className={className} {...props}>
				{children}
			</code>
		);
	},
};

export function LazyMarkdown({
	children,
	components,
	remarkPlugins,
	rehypePlugins,
	...props
}: LazyMarkdownProps) {
	const [modules, setModules] = useState<MarkdownModules | null>(null);

	useEffect(() => {
		void Promise.all([
			import("react-markdown"),
			import("remark-gfm"),
			import("rehype-raw"),
			import("rehype-sanitize"),
		]).then(([md, gfm, raw, sanitize]) => {
			setModules({
				Markdown: md.default,
				// Inline `data:image/*` sources are kept for `<img>` so base64-encoded
				// figures render; every other URL goes through the default transform.
				urlTransform: buildUrlTransform(md.defaultUrlTransform),
				remarkPlugins: [gfm.default],
				// `rehype-raw` parses HTML embedded in the markdown so it renders as
				// markup instead of text; `rehype-sanitize` runs after it to drop
				// anything unsafe.
				rehypePlugins: [
					raw.default,
					[
						sanitize.default,
						{
							...sanitize.defaultSchema,
							// `remark-rehype` already prefixes the ids it generates for GFM
							// footnotes. Prefixing them again here would leave the footnote
							// links pointing at ids that no longer exist.
							clobberPrefix: "",
							protocols: {
								...sanitize.defaultSchema.protocols,
								src: [...(sanitize.defaultSchema.protocols?.src ?? []), "data"],
							},
						},
					],
				],
			});
		});
	}, []);

	const mergedComponents = useMemo<Components>(
		() => ({ ...mermaidComponents, ...components }),
		[components],
	);

	const mergedRemarkPlugins = useMemo(
		() => [...(modules?.remarkPlugins ?? []), ...(remarkPlugins ?? [])],
		[modules, remarkPlugins],
	);

	const mergedRehypePlugins = useMemo(
		() => [...(modules?.rehypePlugins ?? []), ...(rehypePlugins ?? [])],
		[modules, rehypePlugins],
	);

	if (!modules) {
		return <Skeleton className="min-h-[100px]" />;
	}

	const { Markdown, urlTransform } = modules;

	return (
		<Markdown
			urlTransform={urlTransform}
			remarkPlugins={mergedRemarkPlugins}
			rehypePlugins={mergedRehypePlugins}
			components={mergedComponents}
			{...props}
		>
			{children}
		</Markdown>
	);
}
