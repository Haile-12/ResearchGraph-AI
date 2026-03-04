import React from 'react';
export default function TypingIndicator({ label = 'Thinking' }) {
    return (
        <div className="message-wrapper assistant" style={{ marginBottom: '0.5rem' }}>
            <div className="message-avatar" style={{ background: 'var(--grad-main)', fontSize: '18px' }}>
                🧠
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <div className="typing-indicator">
                    <div className="typing-dots">
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                        <div className="typing-dot" />
                    </div>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '0.25rem' }}>
                        {label}…
                    </span>
                </div>
            </div>
        </div>
    );
}
