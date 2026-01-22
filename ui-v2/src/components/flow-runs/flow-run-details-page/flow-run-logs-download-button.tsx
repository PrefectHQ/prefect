import { useState } from "react";
import { toast } from "sonner";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";

type FlowRunLogsDownloadButtonProps = {
	flowRun: components["schemas"]["FlowRunResponse"];
};

export function FlowRunLogsDownloadButton({
	flowRun,
}: FlowRunLogsDownloadButtonProps) {
	const [isDownloading, setIsDownloading] = useState(false);

	const handleDownload = async () => {
		setIsDownloading(true);
		try {
			const service = await getQueryService();
			const response = await service.GET("/flow_runs/{id}/logs/download", {
				params: { path: { id: flowRun.id } },
				parseAs: "blob",
			});

			if (!response.data) {
				throw new Error("No data received from server");
			}

			const url = URL.createObjectURL(response.data);
			const link = document.createElement("a");
			const filename = flowRun.name ?? "logs";

			link.href = url;
			link.setAttribute("download", `${filename}.csv`);
			link.click();

			URL.revokeObjectURL(url);
		} catch (error) {
			console.error(error);
			toast.error("Failed to download logs");
		} finally {
			setIsDownloading(false);
		}
	};

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					variant="outline"
					size="icon"
					onClick={() => void handleDownload()}
					disabled={isDownloading}
					aria-label="Download logs"
				>
					{isDownloading ? (
						<Icon id="Loader2" className="size-4 animate-spin" />
					) : (
						<Icon id="Download" className="size-4" />
					)}
				</Button>
			</TooltipTrigger>
			<TooltipContent>Download all logs as CSV</TooltipContent>
		</Tooltip>
	);
}
