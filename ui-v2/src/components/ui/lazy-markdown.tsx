import { useEffect, useState } from "react";
import type { Options } from "react-markdown";
import { Skeleton } from "@/components/ui/skeleton";

type LazyMarkdownProps = Omit<Options, "children"> & {
	children: string;
};

export function LazyMarkdown({ children, ...props }: LazyMarkdownProps) {
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

	if (!Component || !plugin) {
		return <Skeleton className="min-h-[100px]" />;
	}

	return (
		<Component remarkPlugins={[plugin]} {...props}>
			{children}
		</Component>
	);
}
