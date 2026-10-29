export interface UserSession {
    id: string;
    email?: string | null;
    name: string;
    avatarUrl?: string | null;
    isGuest: boolean;
    createdAt: string;
    lastSeenAt: string;
}

export interface GuestPassRequest {
    deviceId?: string | null;
}

export interface AuthTokens {
    accessToken: string;
    tokenType: string;
    expiresIn: number;
}

export interface GuestPassResponse {
    user: UserSession;
    tokens: AuthTokens;
    quotaRemaining: number;
    bucketCapacity: number;
}

export interface TokenResponse {
    accessToken: string;
    tokenType: string;
    expiresIn: number;
    user: UserSession;
    quotaRemaining?: number;
    bucketCapacity?: number;
}

export interface QuotaStatus {
    tokensRemaining: number;
    bucketCapacity: number;
    resetMinutes: number;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    email: string;
    password: string;
    name: string;
}

export interface GoogleAuthRequest {
    credential: string;
}
