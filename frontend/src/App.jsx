import React, { useCallback, useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import LandingPage from './components/Landing/LandingPage';
import Sidebar from './components/Sidebar/Sidebar';
import ChatInterface from './components/Chat/ChatInterface';
import { useSession } from './hooks/useSession';
import { useChat } from './hooks/useChat';
export default function App() {
    return (
        <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/app/*" element={<AppShell />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
function AppShell() {
    const navigate = useNavigate();
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const {
        sessions,
        activeSessionId,
        createNewSession,
        selectSession,
        deleteSession,
        updateLastQuery,
    } = useSession();
    const {
        messages,
        isLoading,
        sendMessage,
        loadMore,
        clearMessages,
    } = useChat(activeSessionId);
    const handleSend = useCallback(async (question, opts) => {
        let sId = activeSessionId;
        if (!sId) {
            sId = await createNewSession();
            if (!sId) return; 
        }
        updateLastQuery(sId, question);
        await sendMessage(question, opts, sId);
    }, [activeSessionId, createNewSession, sendMessage, updateLastQuery]);
    const handleNewSession = useCallback(() => {
        createNewSession();
        clearMessages();
        setSidebarOpen(false); 
    }, [createNewSession, clearMessages]);
    const handleSelectSession = useCallback((id) => {
        selectSession(id);
        clearMessages();
        setSidebarOpen(false); 
    }, [selectSession, clearMessages]);
    useEffect(() => {
        document.title = 'ResearchGraph AI - Knowledge Graph Query System';
    }, []);
    return (
        <div className={`app-shell ${sidebarOpen ? 'sidebar-open' : ''}`}>
            <div className="mobile-header d-md-none">
                <button
                    className="mobile-menu-btn"
                    onClick={() => setSidebarOpen(true)}
                    aria-label="Open menu"
                >
                    <Menu size={20} />
                </button>
                <div className="mobile-brand" onClick={() => navigate('/')}>
                    ResearchGraph
                </div>
                <div style={{ width: 32 }} /> 
            </div>
            {sidebarOpen && (
                <div
                    className="sidebar-backdrop d-md-none"
                    onClick={() => setSidebarOpen(false)}
                />
            )}
            <div className={`sidebar-container ${sidebarOpen ? 'open' : ''}`}>
                {sidebarOpen && (
                    <button
                        className="sidebar-close-btn d-md-none"
                        onClick={() => setSidebarOpen(false)}
                    >
                        <X size={20} />
                    </button>
                )}
                <Sidebar
                    sessions={sessions}
                    activeSessionId={activeSessionId}
                    onNewSession={handleNewSession}
                    onSelectSession={handleSelectSession}
                    onDeleteSession={deleteSession}
                />
            </div>
            <main className="main-content">
                <ChatInterface
                    messages={messages}
                    isLoading={isLoading}
                    onSend={handleSend}
                    onLoadMore={loadMore}
                />
            </main>
        </div>
    );
}
