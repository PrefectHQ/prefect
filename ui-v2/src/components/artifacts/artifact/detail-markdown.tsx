import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type DetailMarkdownProps = {
	markdown: string;
};

export const DetailMarkdown = ({ markdown }: DetailMarkdownProps) => {
	return (
		<div data-testid="markdown-display" className="prose">
			<Markdown remarkPlugins={[remarkGfm]} className={"prose lg:prose-xl"}>
				{markdown}
			</Markdown>
		</div>
	);
};
