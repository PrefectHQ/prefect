import { useQuery } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { buildGetSettingsQuery } from "@/api/admin";
import { Card } from "@/components/ui/card";
import { cn } from "@/utils";

type DashboardMarketingBannerProps = {
	title: string;
	subtitle: string;
	actions: ReactNode;
	className?: string;
};

export const DashboardMarketingBanner = ({
	title,
	subtitle,
	actions,
	className,
}: DashboardMarketingBannerProps): JSX.Element | null => {
	const { data: settings } = useQuery(buildGetSettingsQuery());

	if (!settings) {
		return null;
	}

	const server = (settings as Record<string, unknown>).server as
		| Record<string, unknown>
		| undefined;
	const ui = server?.ui as Record<string, unknown> | undefined;
	const showPromotionalContent =
		(ui?.show_promotional_content as boolean | undefined) ?? true;

	if (!showPromotionalContent) {
		return null;
	}

	return (
		<Card
			className={cn(
				"relative overflow-hidden p-4",
				"bg-[url('/marketing-banner-bg-light.svg')] dark:bg-[url('/marketing-banner-bg-dark.svg')]",
				"bg-no-repeat bg-right-top [background-size:auto_100%]",
				className,
			)}
		>
			<div className="relative z-[2] flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
				<div className="flex flex-col gap-2">
					<h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
					<div className="text-base text-muted-foreground">{subtitle}</div>
				</div>
				<div className="flex flex-shrink-0 flex-col gap-2">{actions}</div>
			</div>
		</Card>
	);
};
