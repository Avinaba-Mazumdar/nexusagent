import type { DocumentChunkWire, DocumentListResponseWire, DocumentMetadataWire, DocumentUploadResponseWire } from './generated';

export type DocumentMetadata = DocumentMetadataWire;
export type DocumentChunkResponse = DocumentChunkWire;
export type DocumentChunkMetadata = DocumentChunkWire['metadata'];
export type DocumentUploadResponse = DocumentUploadResponseWire;
export type DocumentListResponse = DocumentListResponseWire;
