import React, { useEffect, useRef, useState } from 'react';
import { Network, Search, Zap, Bot, ShieldQuestion } from 'lucide-react';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import InputDock from './InputDock';
export default function ChatInterface({ messages, isLoading, onSend, onLoadMore }) {
    const listRef = useRef(null);
    const [editValue, setEditValue] = useState('');
    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = listRef.current.scrollHeight;
        }
    }, [messages, isLoading]);
    return (
        <div className="chat-card">
            <div className="chat-main-view">
                {messages.length === 0 && !isLoading ? (
                    <div className="welcome-state">
                        <div className="welcome-hero-bg" />
                        <h1 className="welcome-title">
                            Research <span className="text-gradient">Literature Graph</span>
                        </h1>
                        <p className="welcome-subtitle">
                            Search across papers, authors, and citations using natural language.
                        </p>
                    </div>
                ) : (
                    <div className="messages-list" ref={listRef}>
                        {messages.map(msg => (
                            <MessageBubble
                                key={msg.id}
                                message={msg}
                                onLoadMore={onLoadMore}
                                onEdit={(val) => setEditValue(val)}
                            />
                        ))}
                        {isLoading && <TypingIndicator label="Querying knowledge graph" />}
                    </div>
                )}
            </div>
            <div className="chat-input-sticky">
                <InputDock
                    onSend={onSend}
                    isLoading={isLoading}
                    externalValue={editValue}
                    onExternalValueClear={() => setEditValue('')}
                />
            </div>
        </div>
    );
}
