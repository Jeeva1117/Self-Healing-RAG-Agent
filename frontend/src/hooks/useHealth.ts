import { useQuery } from '@tanstack/react-query';
import { healthService } from '@/services/healthService';

export function useSystemHealth() {
  const healthQuery = useQuery({
    queryKey: ['system', 'health'],
    queryFn: healthService.getHealth,
    refetchInterval: 15000,
    retry: 2,
  });

  const readinessQuery = useQuery({
    queryKey: ['system', 'readiness'],
    queryFn: healthService.getReadiness,
    refetchInterval: 15000,
    retry: 2,
  });

  const systemInfoQuery = useQuery({
    queryKey: ['system', 'info'],
    queryFn: healthService.getSystemInfo,
    staleTime: 60000,
  });

  return {
    health: healthQuery.data,
    readiness: readinessQuery.data,
    systemInfo: systemInfoQuery.data,
    isLoading: healthQuery.isLoading || readinessQuery.isLoading,
    isError: healthQuery.isError || readinessQuery.isError,
    error: healthQuery.error || readinessQuery.error,
    refetch: () => {
      healthQuery.refetch();
      readinessQuery.refetch();
    },
  };
}
