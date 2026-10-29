export interface DocumentMetadata {
    id: string;
    userId?: string | null;
    filename: string;
    mimeType: string;
    sha256Hash: string;
    totalChunks: number;
    isSeeded: boolean;
    uploadedAt: string;
}

export interface DocumentChunkMetadata {
    headerPath?: string[];
    startLine?: number;
    endLine?: number;
    charCount?: number;
    tokenCount?: number;
    sha256?: string;
    [key: string]: unknown;
}

export interface DocumentChunkResponse {
    id: string;
    documentId: string;
    chunkIndex: number;
    content: string;
    metadata: DocumentChunkMetadata;
    createdAt: string;
}

export interface DocumentUploadResponse {
    document: DocumentMetadata;
    chunksCount: number;
    previewChunks: DocumentChunkResponse[];
}

export interface DocumentListResponse {
    documents: DocumentMetadata[];
}
