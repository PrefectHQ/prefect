import { Link } from "@tanstack/react-router";
import { useCallback } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";
import { Icon } from "@/components/ui/icons";
import {
	Menubar,
	MenubarContent,
	MenubarItem,
	MenubarMenu,
	MenubarTrigger,
} from "@/components/ui/menubar";
import { Typography } from "@/components/ui/typography";

type ArtifactsKeyHeaderProps = {
	artifactKey: string;
	pageHeader?: string;
};

export const ArtifactsKeyHeader = ({
	artifactKey,
	pageHeader,
}: ArtifactsKeyHeaderProps) => {
	const handleCopyId = useCallback(() => {
		void navigator.clipboard.writeText(artifactKey);
	}, [artifactKey]);

	return (
		<>
			<div className="flex items-center justify-between">
				<Header artifactKey={artifactKey} />
				<div className="flex items-center space-x-2">
					<DocsLink id="artifacts-guide" label="Documentation" />
					{/* <Button variant="outline" className="px-1"><Icon id="EllipsisVertical" /></Button> */}
					<Menubar>
						<MenubarMenu>
							<MenubarTrigger className="px-1">
								<Icon id="EllipsisVertical" />
							</MenubarTrigger>
							<MenubarContent>
								<MenubarItem onClick={handleCopyId}>Copy Id</MenubarItem>
							</MenubarContent>
						</MenubarMenu>
					</Menubar>
				</div>
			</div>
			{pageHeader && (
				<div className="">
					<Typography variant="h2" className="my-4 font-bold prose lg:prose-xl">
						<Markdown remarkPlugins={[remarkGfm]}>{pageHeader}</Markdown>
					</Typography>
					<hr />
				</div>
			)}
		</>
	);
};

const Header = ({ artifactKey }: ArtifactsKeyHeaderProps) => (
	<div className="flex items-center ">
		<Breadcrumb>
			<BreadcrumbList>
				<Link to={"/artifacts"}>
					<BreadcrumbItem className="text-xl font-bold text-blue-700 hover:underline">
						Artifacts
					</BreadcrumbItem>
				</Link>
				<BreadcrumbSeparator>/</BreadcrumbSeparator>
				<BreadcrumbItem className="text-xl font-bold text-black">
					{artifactKey}
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
