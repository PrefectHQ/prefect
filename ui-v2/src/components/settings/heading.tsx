import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

type HeadingProps = {
	version: string;
};

export const Heading = ({ version }: HeadingProps) => {
	return (
		<div className="flex justify-between items-center">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem className="text-xl font-semibold">
						Settings
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<div className="flex flex-col gap-1">
				<div className="text-xs text-muted-foreground">Version</div>
				<div className="text-xs">{version}</div>
			</div>
		</div>
	);
};
