import { Badge } from "@/components/ui/badge";
import type { components } from "@/api/prefect";
import type { CellContext, Row } from "@tanstack/react-table";
import { getQueryService } from "@/api/service";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";

export const StatusCell = ({ getValue }: CellContext<components["schemas"]["WorkPool"], boolean>) => {
    const isPaused = getValue();
    return (
        <Badge variant={isPaused ? "secondary" : "default"}>
            {isPaused ? "Paused" : "Running"}
        </Badge>
    );
};

export const ConcurrencyCell = ({ getValue }: CellContext<components["schemas"]["WorkPool"], number | null>) => {
    const limit = getValue();
    return limit === null ? "∞" : limit;
};

export const UpdatedCell = ({ getValue }: CellContext<components["schemas"]["WorkPool"], string>) => {
    const updated = getValue();
    if (!updated) return null;
    return new Date(updated)
        .toLocaleString(undefined, {
            year: "numeric",
            month: "numeric",
            day: "numeric",
            hour: "numeric",
            minute: "numeric",
            second: "numeric",
            hour12: true,
        })
        .replace(",", "");
};

export const LastHeartbeatCell = ({ row }: { row: Row<components["schemas"]["WorkPool"]> }) => {
    const workPoolName = row.original.name;
    const { data: workers } = useSuspenseQuery({
        queryKey: ["work-pool-workers", workPoolName],
        queryFn: async () => {
            const response = await getQueryService().POST('/work_pools/{work_pool_name}/workers/filter', {
                params: {
                    path: {
                        work_pool_name: workPoolName
                    }
                }
            });
            return response.data as components["schemas"]["WorkerResponse"][]
        },
        staleTime: 1000
    });

    if (!workers?.length) return "No workers";

    // Since workers come ordered by heartbeat, first worker has latest heartbeat
    const latestHeartbeat = workers[0].last_heartbeat_time;

    if (!latestHeartbeat) return "Never";

    return new Date(latestHeartbeat)
        .toLocaleString(undefined, {
            year: "numeric",
            month: "numeric", 
            day: "numeric",
            hour: "numeric",
            minute: "numeric",
            second: "numeric",
            hour12: true,
        })
        .replace(",", "");
};

export const ActionsCell = ({ row }: CellContext<components["schemas"]["WorkPool"], unknown>) => {
    const workPool = row.original
    const queryClient = useQueryClient();
    const { toast } = useToast();

    const togglePauseMutation = useMutation({
        mutationFn: async () => {
            const service = getQueryService();
            await service.PATCH('/work_pools/{name}', {
                params: {
                    path: {
                        name: workPool.name
                    }
                },
                body: {
                    is_paused: !workPool.is_paused
                }
            });
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['work-pools'] });
            toast({
                title: `Work pool ${workPool.is_paused ? 'resumed' : 'paused'}`,
                description: `${workPool.name} has been ${workPool.is_paused ? 'resumed' : 'paused'}`
            });
        }
    });

    return (
        <div className="flex items-center gap-2 justify-end">
            <Switch
                checked={!workPool.is_paused}
                onCheckedChange={() => void togglePauseMutation.mutate()}
                aria-label={`${workPool.is_paused ? 'Resume' : 'Pause'} work pool`}
            />
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="h-8 w-8 p-0">
                        <MoreHorizontal className="h-4 w-4" />
                        <span className="sr-only">Open menu</span>
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuItem asChild>
                        <Link to="/work-pools/work-pool/$name" params={{ name: workPool.name }}>
                            Edit
                        </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                        onClick={() => {
                            if (workPool.id) {
                                void navigator.clipboard.writeText(workPool.id);
                                toast({
                                    title: "ID copied", 
                                    description: "Work pool ID copied to clipboard"
                                });
                            }
                        }}
                    >
                        Copy ID
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    );
};