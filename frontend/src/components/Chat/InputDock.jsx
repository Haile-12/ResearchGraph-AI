import React, { useState, useRef, useEffect } from 'react';
import { Send, CornerDownLeft, Network, Search, Zap, Bot, Sparkles } from 'lucide-react';
const QUERY_TYPES = [
    { value: null, label: 'Auto', icon: <Sparkles size={14} />, color: '#64748b' },
    { value: 'GRAPH_TRAVERSAL', label: 'Graph', icon: <Network size={14} />, color: '#3b82f6' },
    { value: 'VECTOR_SIMILARITY', label: 'Semantic', icon: <Search size={14} />, color: '#8b5cf6' },
    { value: 'HYBRID', label: 'Hybrid', icon: <Zap size={14} />, color: '#f97316' },
    { value: 'AGENT_COMPLEX', label: 'Agent', icon: <Bot size={14} />, color: '#10b981' },
];
export default function InputDock({ onSend, isLoading, externalValue, onExternalValueClear }) {
    const [input, setInput] = useState('');
    const [forceType, setForceType] = useState(null);
    const [showTypes, setShowTypes] = useState(false);
    const textareaRef = useRef(null);
    useEffect(() => { textareaRef.current?.focus(); }, []);
    useEffect(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }, [input]);
    useEffect(() => {
        if (externalValue) {
            setInput(externalValue);
            onExternalValueClear?.();
            textareaRef.current?.focus();
        }
    }, [externalValue, onExternalValueClear]);
    const handleSend = () => {
        const q = input.trim();
        if (!q || isLoading) return;
        onSend(q, { forceType });
        setInput('');
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
    };
    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };
    const activeType = QUERY_TYPES.find(t => t.value === forceType);
    return (
        <div className="chat-input-area">
            <div className="chat-input-wrapper">
                <div className="input-glass">
                    <div className="type-selector-wrapper" style={{ position: 'relative', flexShrink: 0 }}>
                        <button
                            className="type-badge-inline"
                            onClick={() => setShowTypes(v => !v)}
                            title={activeType?.label}
                            style={{
                                color: activeType?.color || '#94a3b8',
                                background: showTypes ? 'var(--border-subtle)' : 'transparent'
                            }}
                        >
                            {activeType?.icon}
                        </button>
                        {showTypes && (
                            <div className="type-dropdown">
                                {QUERY_TYPES.map(t => (
                                    <button
                                        key={t.label}
                                        className="type-dropdown-item"
                                        onClick={() => { setForceType(t.value); setShowTypes(false); }}
                                        style={{
                                            background: forceType === t.value ? 'var(--border-subtle)' : 'transparent',
                                            color: t.color,
                                        }}
                                    >
                                        {t.icon} {t.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    <textarea
                        ref={textareaRef}
                        className="chat-input"
                        placeholder="Ask anything about the research knowledge graph…"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isLoading}
                        rows={1}
                        style={{ maxHeight: '140px', overflowY: 'auto' }}
                        id="chat-input-main"
                    />
                    <button
                        className="send-btn"
                        onClick={handleSend}
                        disabled={isLoading || !input.trim()}
                        aria-label="Send message"
                        id="send-btn"
                    >
                        {isLoading
                            ? <div className="animate-spin" style={{ width: 22, height: 22, border: '2.5px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
                            : <Send size={20} strokeWidth={2.5} />
                        }
                    </button>
                </div>
            </div>
        </div>
    );
}
