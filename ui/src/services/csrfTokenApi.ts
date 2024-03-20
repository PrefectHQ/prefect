import { AxiosInstance, InternalAxiosRequestConfig, isAxiosError } from 'axios';
import { randomId, showToast } from '@prefecthq/prefect-design';
import { Api, AxiosInstanceSetupHook, PrefectConfig } from '@prefecthq/prefect-ui-library'

export type CsrfToken = {
    token: string
    expiration: Date
    client: string
    issued: Date
}

export type CsrfTokenResponse = {
    token: string;
    expiration: Date;
}

export class CsrfTokenApi extends Api {
    public csrfToken?: CsrfToken
    public csrfSupportEnabled = true;
    private refreshTimeout: ReturnType<typeof setTimeout> | null = null;
    private ongoingRefresh: Promise<void> | null = null;

    public constructor(apiConfig: PrefectConfig, instanceSetupHook: AxiosInstanceSetupHook | null = null) {
        super(apiConfig, instanceSetupHook)
        this.startBackgroundTokenRefresh()
    }

    public async addCsrfHeaders(config: InternalAxiosRequestConfig) {
        if (this.csrfSupportEnabled) {
            await this.refreshCsrfToken()
            config.headers = config.headers || {}
            config.headers['Prefect-Csrf-Token'] = this.csrfToken.token
            config.headers['Prefect-Csrf-Client'] = this.csrfToken.client
        }
    }

    private async refreshCsrfToken(force: boolean = false) {
        if (!force && !this.shouldRefreshToken()) {
            return this.ongoingRefresh ?? Promise.resolve();
        }

        if (this.ongoingRefresh) {
            return this.ongoingRefresh;
        }

        const refresh = async () => {
            try {
                const response = await this.get<CsrfTokenResponse>(`/csrf-token?client=${this.csrfToken.client}`);
                const now = new Date();
                this.csrfToken.token = response.data.token;
                this.csrfToken.expiration = response.data.expiration;
                this.csrfToken.issued = new Date();
                this.ongoingRefresh = null;
            } catch (error) {
                this.ongoingRefresh = null;
                if (isAxiosError(error)) {
                    const status = error.response?.status;
                    const unconfiguredServer = status === 422 && error.response?.data.detail.includes('CSRF protection is disabled.');

                    if (unconfiguredServer) {
                        this.disableCsrfSupport()
                    } else {
                        console.error('Failed to refresh CSRF token:', error)
                        showToast('Failed to refresh CSRF token')
                        throw new Error('Failed to refresh CSRF token')
                    }
                }
            }
        };

        this.ongoingRefresh = refresh();
        return this.ongoingRefresh;
    }

    private shouldRefreshToken(): boolean {
        if(!this.csrfSupportEnabled) {
          return false
        }
        
        if(!this.csrfToken.token || !this.csrfToken.expiration) {
          return true
        }
        
        const now = new Date()
        
        return now > this.csrfToken.expiration
    }

    private disableCsrfSupport() {
        this.csrfSupportEnabled = false
    }

    private startBackgroundTokenRefresh() {
        const calculateTimeoutDuration = () => {
            if (this.csrfToken.expiration && this.csrfToken.issued) {
                const now = new Date()
                const expiration = new Date(this.csrfToken.expiration)
                const issuedAt = this.csrfToken.issued
                const lifetime = expiration.getTime() - issuedAt.getTime()
                const refreshThreshold = issuedAt.getTime() + lifetime * 0.75
                const durationUntilRefresh = refreshThreshold - now.getTime()

                return durationUntilRefresh
            }
            return 0; // If we don't have token data cause an immediate refresh
        };

        const refreshTask = async () => {
            if (this.csrfSupportEnabled) {
                await this.refreshCsrfToken(true)
                this.refreshTimeout = setTimeout(refreshTask, calculateTimeoutDuration())
            }
        };

        this.refreshTimeout = setTimeout(refreshTask, calculateTimeoutDuration())
    }
}

export function setupCsrfInterceptor(csrfTokenApi: CsrfTokenApi, axiosInstance: AxiosInstance) {
    axiosInstance.interceptors.request.use(async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
        const method = config.method?.toLowerCase();

        if (method && ['post', 'patch', 'put', 'delete'].includes(method)) {
            await csrfTokenApi.addCsrfHeaders(config)
        }

        return config
    })
}
