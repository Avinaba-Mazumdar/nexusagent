import type { DocumentChunksResponseWire, DocumentChunkWire, DocumentListResponseWire, DocumentMetadataWire, DocumentUploadResponseWire } from './generated';

export type DocumentMetadata = DocumentMetadataWire;
export type DocumentChunkResponse = DocumentChunkWire;
export type DocumentChunkMetadata = DocumentChunkWire['metadata'];
export type DocumentChunksResponse = DocumentChunksResponseWire;
export type DocumentUploadResponse = DocumentUploadResponseWire;
export type DocumentListResponse = DocumentListResponseWire;
