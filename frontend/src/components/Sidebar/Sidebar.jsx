import React, { useEffect, useState } from 'react';
import { Plus, Sparkles, MessageSquarePlus, AlignLeft, Hexagon, History, LogOut } from 'lucide-react';
import SessionItem from './SessionItem';
import { getSuggestions } from '../../services/api';
import ThemeToggle from '../Theme/ThemeToggle';
export default function Sidebar({
    sessions,
    activeSessionId,
    onSelectSession,
    onNewSession,
    onDeleteSession,
}) {
    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                        <div style={{
                            width: '32px', height: '32px', borderRadius: '10px',
                            background: 'var(--grad-main)', display: 'flex',
                            alignItems: 'center', justifyContent: 'center', color: 'white',
                            boxShadow: '0 4px 10px rgba(16,185,129,0.2)'
                        }}>
                            <Hexagon size={18} fill="currentColor" />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-dark)', letterSpacing: '-0.3px', lineHeight: 1.2 }}>
                                ResearchGraph
                            </div>
                            <ThemeToggle iconOnly={true} />
                        </div>
                    </div>
                </div>
                <button
                    className="new-chat-btn"
                    onClick={onNewSession}
                    id="new-chat-btn"
                >
                    <Plus size={16} />
                    <span>New Chat</span>
                </button>
            </div>
            <div className="sidebar-scroll">
                <div className="sidebar-group">
                    <div className="sidebar-group-title">
                        <History size={12} /> Recent Chats
                    </div>
                    {sessions.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '2rem 0', color: '#94a3b8', fontSize: '0.85rem', fontWeight: 500 }}>
                            No chat history
                        </div>
                    ) : (
                        <div className="sidebar-session-list">
                            {sessions.map(session => (
                                <SessionItem
                                    key={session.id}
                                    session={session}
                                    isActive={session.id === activeSessionId}
                                    onSelect={onSelectSession}
                                    onDelete={onDeleteSession}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
            <div className="sidebar-footer">
                <button className="logout-btn" onClick={() => window.location.href = '/'}>
                    <LogOut size={16} />
                    <span>Log out</span>
                </button>
            </div>
        </aside>
    );
}
