export interface DependencyHealth {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'disabled';
  connected: boolean;
  latency_ms?: number | null;
  details?: Record<string, unknown> | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface LivenessResponse {
  status: string;
  service: string;
  uptime_seconds: number;
}

export interface ReadinessResponse {
  status: 'ready' | 'degraded' | 'not_ready';
  service: string;
  ready: boolean;
  dependencies: {
    database: DependencyHealth;
    redis: DependencyHealth;
  };
}

export interface SystemInfoResponse {
  service: string;
  version: string;
  environment: string;
  python_version: string;
  features: Record<string, boolean>;
}
