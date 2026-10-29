'use client';

import * as React from 'react';
import Link from 'next/link';
import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight, Database, FileText, Loader2, MessageSquare, Terminal, UploadCloud } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { McpInspector } from '@/components/mcp';
import { SidebarChatHistory } from '@/components/sidebar';
import type { ChatConversation } from '@nexusagent/contracts';

export interface WorkspaceDoc {
    id: string;
    filename: string;
    totalChunks: number;
    isSeeded: boolean;
}

export type UploadState = { status: 'idle' } | { status: 'uploading' | 'success' | 'error'; message: string };

interface CollapsibleSectionProps {
    id: string;
    title: string;
    icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>;
    badge?: React.ReactNode;
    isOpen: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}

export function CollapsibleSection({ id, title, icon: Icon, badge, isOpen, onToggle, children }: CollapsibleSectionProps) {
    const contentId = `category-${id}-content`;
    return (
        <div className="rounded-xl border border-border/70 bg-card overflow-hidden shadow-2xs">
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={isOpen}
                aria-controls={contentId}
                className="w-full h-10 px-3 flex items-center justify-between text-xs font-medium text-foreground hover:bg-secondary/50 transition-colors cursor-pointer select-none"
            >
                <div className="flex items-center gap-2">
                    <Icon className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                    <span className="font-heading font-semibold text-xs text-foreground">{title}</span>
                    {badge}
                </div>
                {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                )}
            </button>
            {isOpen && children}
        </div>
    );
}

export interface WorkspaceSidebarProps {
    mobileActiveTab: 'workspace' | 'chat' | 'observability';
    openCategories: { documents: boolean; chats: boolean; mcp: boolean };
    onToggleCategory: (category: 'documents' | 'chats' | 'mcp') => void;
    docs: WorkspaceDoc[];
    docsError: string | null;
    selectedCitationDoc: string | null;
    token: string | null;
    uploadState: UploadState;
    fileInputRef: React.RefObject<HTMLInputElement | null>;
    onUploadClick: () => void;
    onFileSelected: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onInquireAuthor: () => void;
    // Chats
    isGoogleUser: boolean;
    activeSessionId: string | null;
    conversations: ChatConversation[];
    isLoadingConversations: boolean;
    chatSearchQuery: string;
    onSearchChange: (query: string) => void;
    onSelectConversation: (conv: ChatConversation) => void;
    onDeleteConversation: (convId: string) => void;
    onPrefetchConversation: (convId: string) => void;
    onOpenSignIn: () => void;
    chatNotice: string | null;
    apiBase: string;
}

export function WorkspaceSidebar({
    mobileActiveTab,
    openCategories,
    onToggleCategory,
    docs,
    docsError,
    selectedCitationDoc,
    token,
    uploadState,
    fileInputRef,
    onUploadClick,
    onFileSelected,
    onInquireAuthor,
    isGoogleUser,
    activeSessionId,
    conversations,
    isLoadingConversations,
    chatSearchQuery,
    onSearchChange,
    onSelectConversation,
    onDeleteConversation,
    onPrefetchConversation,
    onOpenSignIn,
    chatNotice,
    apiBase
}: WorkspaceSidebarProps) {
    return (
        <aside
            role="complementary"
            aria-label="Workspace"
            className={`w-full xl:w-72 2xl:w-80 bg-card border-r border-border flex flex-col shrink-0 h-full overflow-hidden ${
                mobileActiveTab === 'workspace' ? 'flex' : 'hidden xl:flex'
            }`}
        >
            <div className="flex items-center justify-between p-3.5 pb-2.5 border-b border-border shrink-0">
                <h2 className="flex items-center gap-1.5 text-xs font-heading font-bold text-foreground">
                    <Database className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                    <span>Workspace</span>
                </h2>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2.5 min-h-0">
                {/* a. Documents Collapsible Category */}
                <CollapsibleSection
                    id="documents"
                    title="Documents"
                    icon={FileText}
                    isOpen={openCategories.documents}
                    onToggle={() => onToggleCategory('documents')}
                    badge={
                        <Badge variant="soft" className="text-[10px] font-mono py-0 px-1.5">
                            {docs.length}
                        </Badge>
                    }
                >
                    <div id="category-documents-content" className="p-3 pt-1 border-t border-border/50 space-y-2">
                        <p className="text-[11px] text-muted-foreground">Pre-indexed AI benchmarks plus your uploads</p>
                        {docsError && (
                            <p className="text-[11px] text-destructive" role="alert">
                                {docsError}
                            </p>
                        )}
                        <div className="space-y-1.5 max-h-35 overflow-y-auto">
                            {docs.map((doc) => {
                                const isSelected = Boolean(selectedCitationDoc && doc.filename.toLowerCase().includes(selectedCitationDoc.toLowerCase()));
                                return (
                                    <div
                                        key={doc.id}
                                        data-selected-doc={isSelected ? 'true' : undefined}
                                        className={`flex items-center justify-between p-2 rounded-lg border text-[11px] transition-all ${
                                            isSelected ? 'bg-primary/15 border-primary shadow-xs ring-1 ring-primary' : 'bg-secondary/40 border-border/70'
                                        }`}
                                    >
                                        <div className="flex items-center gap-1.5 truncate">
                                            <FileText className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                                            <span className={`truncate font-mono ${isSelected ? 'text-primary font-bold' : 'text-foreground'}`}>
                                                {doc.filename}
                                            </span>
                                        </div>
                                        {isSelected ? (
                                            <Badge variant="default" className="text-[10px] px-1 py-0 shrink-0 font-mono">
                                                Cited
                                            </Badge>
                                        ) : (
                                            <Badge variant="outline" className="text-[10px] px-1 py-0 shrink-0">
                                                {doc.isSeeded ? `${doc.totalChunks} chunks` : 'Yours'}
                                            </Badge>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Document Upload */}
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".md,.markdown,.txt,text/markdown,text/plain"
                            onChange={onFileSelected}
                            className="hidden"
                            aria-hidden="true"
                            tabIndex={-1}
                            data-testid="document-upload-input"
                        />
                        <Button
                            variant="default"
                            size="sm"
                            onClick={onUploadClick}
                            disabled={uploadState.status === 'uploading'}
                            className="w-full justify-center gap-1.5 text-xs font-bold rounded-xl mt-2 shadow-2xs h-9 cursor-pointer"
                        >
                            {uploadState.status === 'uploading' ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                            ) : (
                                <UploadCloud className="h-3.5 w-3.5" aria-hidden="true" />
                            )}
                            <span>{token ? 'Upload Markdown (.md, .txt)' : 'Sign in to upload'}</span>
                        </Button>
                        <p className="text-[10px] text-muted-foreground text-center">Max 1 MB. Each upload uses one query.</p>
                        {uploadState.status !== 'idle' && (
                            <p
                                role="status"
                                className={`flex items-start gap-1 text-[11px] ${
                                    uploadState.status === 'error'
                                        ? 'text-destructive'
                                        : uploadState.status === 'success'
                                          ? 'text-success'
                                          : 'text-muted-foreground'
                                }`}
                            >
                                {uploadState.status === 'error' && <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" aria-hidden="true" />}
                                {uploadState.status === 'success' && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-px" aria-hidden="true" />}
                                <span>{uploadState.message}</span>
                            </p>
                        )}

                        {/* Lead Magnet Link */}
                        <button
                            type="button"
                            onClick={onInquireAuthor}
                            className="w-full text-center text-[11px] text-muted-foreground hover:text-primary transition-colors cursor-pointer pt-0.5"
                        >
                            Need custom ETL pipelines? Inquire with author &rarr;
                        </button>
                    </div>
                </CollapsibleSection>

                {/* b. Chats Collapsible Category */}
                <CollapsibleSection
                    id="chats"
                    title="Chats"
                    icon={MessageSquare}
                    isOpen={openCategories.chats}
                    onToggle={() => onToggleCategory('chats')}
                    badge={
                        isGoogleUser && conversations.length > 0 ? (
                            <Badge variant="soft" className="text-[10px] font-mono py-0 px-1.5">
                                {conversations.length}
                            </Badge>
                        ) : null
                    }
                >
                    <div id="category-chats-content" className="p-2.5 pt-1 border-t border-border/50 space-y-1.5">
                        {chatNotice && (
                            <p className="text-[11px] text-destructive" role="alert">
                                {chatNotice}
                            </p>
                        )}
                        <SidebarChatHistory
                            isGoogleUser={isGoogleUser}
                            activeSessionId={activeSessionId}
                            conversations={conversations}
                            isLoading={isLoadingConversations}
                            searchQuery={chatSearchQuery}
                            onSearchChange={onSearchChange}
                            onSelectConversation={onSelectConversation}
                            onDeleteConversation={onDeleteConversation}
                            onPrefetchConversation={onPrefetchConversation}
                            onOpenSignIn={onOpenSignIn}
                        />
                    </div>
                </CollapsibleSection>

                {/* c. MCP Collapsible Category */}
                <CollapsibleSection
                    id="mcp"
                    title="MCP Protocol"
                    icon={Terminal}
                    isOpen={openCategories.mcp}
                    onToggle={() => onToggleCategory('mcp')}
                    badge={
                        <Badge variant="soft" className="text-[10px] font-mono py-0 px-1.5">
                            v2
                        </Badge>
                    }
                >
                    <div id="category-mcp-content" className="p-1 pt-0 border-t border-border/50">
                        <McpInspector apiBase={apiBase} authToken={token} />
                    </div>
                </CollapsibleSection>
            </div>

            {/* d. Bottom Footer (always on bottom) */}
            <div className="shrink-0 p-3 border-t border-border bg-card/80 text-[11px] text-muted-foreground flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Link href="/privacy" className="hover:text-primary transition-colors">
                        Privacy Policy
                    </Link>
                    <span aria-hidden="true">•</span>
                    <Link href="/terms" className="hover:text-primary transition-colors">
                        Terms
                    </Link>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground">nexusagent.avinaba.com</span>
            </div>
        </aside>
    );
}
