import { useEffect, useMemo, useState } from "react";
import type { Components, Options } from "react-markdown";
import { MermaidDiagram } from "@/components/ui/mermaid-diagram";
import { Skeleton } from "@/components/ui/skeleton";

type LazyMarkdownProps = Omit<Options, "children"> & {
	children: string;
};

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
	...props
}: LazyMarkdownProps) {
	const [Component, setComponent] =
		useState<React.ComponentType<Options> | null>(null);
	const [plugin, setPlugin] = useState<
		typeof import("remark-gfm").default | null
	>(null);

	useEffect(() => {
		void Promise.all([import("react-markdown"), import("remark-gfm")]).then(
			([md, gfm]) => {
				setComponent(() => md.default);
				setPlugin(() => gfm.default);
			},
		);
	}, []);

	const mergedComponents = useMemo<Components>(
		() => ({ ...mermaidComponents, ...components }),
		[components],
	);

	if (!Component || !plugin) {
		return <Skeleton className="min-h-[100px]" />;
	}

	return (
		<Component
			remarkPlugins={[plugin]}
			components={mergedComponents}
			{...props}
		>
			{children}
		</Component>
	);
}
