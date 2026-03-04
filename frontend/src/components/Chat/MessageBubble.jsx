import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    User, Bot, Sparkles, Network, Search, Zap,
    CheckCircle2, ChevronDown, ChevronUp, Clock,
    FileText, Copy, Edit2, ThumbsUp, ThumbsDown, Check
} from 'lucide-react';
import ConfidenceGauge from '../Analytics/ConfidenceGauge';
import { formatDuration } from '../../utils/formatters';
const TYPE_ICONS = {
    GRAPH_TRAVERSAL: <Network size={12} />,
    VECTOR_SIMILARITY: <Search size={12} />,
    HYBRID: <Zap size={12} />,
    AGENT_COMPLEX: <Bot size={12} />,
    AMBIGUOUS: <Sparkles size={12} />,
};
const TYPE_LABELS = {
    GRAPH_TRAVERSAL: 'Graph Query',
    VECTOR_SIMILARITY: 'Semantic',
    HYBRID: 'Hybrid',
    AGENT_COMPLEX: 'AI Agent',
    AMBIGUOUS: 'Clarify',
};
export default function MessageBubble({ message, onLoadMore, onEdit }) {
    const [showSteps, setShowSteps] = useState(false);
    const [showExplain, setShowExplain] = useState(false);
    const [copied, setCopied] = useState(false);
    const [rating, setRating] = useState(null); 
    const isUser = message.role === 'user';
    const typeLabel = message.queryType ? (TYPE_LABELS[message.queryType] || message.queryType) : null;
    const typeIcon = message.queryType ? TYPE_ICONS[message.queryType] : null;
    const hasValidation = message.validation && message.queryType === 'GRAPH_TRAVERSAL';
    const hasMore = message.pagination?.has_more;
    const hasSteps = message.agentSteps?.length > 0;
    const handleCopy = () => {
        navigator.clipboard.writeText(message.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <div className={`message-wrapper ${message.role}`}>
            <div className="message-avatar">
                {isUser ? <User size={20} color="white" /> : <Bot size={22} color="white" />}
            </div>
            <div className="message-content-col">
                <div className="message-nameplate">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="message-author">{isUser ? 'You' : 'ResearchGraph AI'}</span>
                        <span className="message-time">
                            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                    <div className="message-actions-inline">
                        <button className="msg-action-btn" onClick={handleCopy} title="Copy to clipboard">
                            {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />}
                        </button>
                        {isUser && onEdit && (
                            <button className="msg-action-btn" onClick={() => onEdit(message.content)} title="Edit and resend">
                                <Edit2 size={14} />
                            </button>
                        )}
                        {!isUser && (
                            <>
                                <button
                                    className={`msg-action-btn ${rating === 'up' ? 'active' : ''}`}
                                    onClick={() => setRating(rating === 'up' ? null : 'up')}
                                >
                                    <ThumbsUp size={14} fill={rating === 'up' ? "currentColor" : "none"} />
                                </button>
                                <button
                                    className={`msg-action-btn ${rating === 'down' ? 'active' : ''}`}
                                    onClick={() => setRating(rating === 'down' ? null : 'down')}
                                >
                                    <ThumbsDown size={14} fill={rating === 'down' ? "currentColor" : "none"} />
                                </button>
                            </>
                        )}
                    </div>
                </div>
                <div className="message-bubble">
                    <div className="message-text">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content}
                        </ReactMarkdown>
                    </div>
                </div>
                {!isUser && (
                    <div className="message-extras">
                        <div className="message-meta-tags">
                            {typeLabel && (
                                <span className={`meta-tag type-${message.queryType?.toLowerCase() || 'default'}`}>
                                    {typeIcon} {typeLabel}
                                </span>
                            )}
                            {message.cached && (
                                <span className="meta-tag cached"><Zap size={12} fill="currentColor" /> Cached</span>
                            )}
                            {message.executionMs > 0 && (
                                <span className="meta-tag time">
                                    <Clock size={12} /> {formatDuration(message.executionMs)}
                                </span>
                            )}
                            {message.isPageResult && (
                                <span className="meta-tag info"><FileText size={12} /> Page {message.page}</span>
                            )}
                        </div>
                        {hasValidation && (
                            <ConfidenceGauge
                                score={message.validation.confidence_score}
                                issues={message.validation.issues}
                                cypher={message.validation.cypher_used}
                                retries={message.validation.retries}
                            />
                        )}
                        {message.explanation && message.explanation.length > 10 && (
                            <div className="collapsible-section">
                                <button className="collapse-btn" onClick={() => setShowExplain(!showExplain)}>
                                    {showExplain ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    <span>{showExplain ? 'Hide' : 'Show'} reasoning</span>
                                </button>
                                {showExplain && (
                                    <div className="collapse-content glass-panel-sub">
                                        {message.explanation}
                                    </div>
                                )}
                            </div>
                        )}
                        {hasSteps && (
                            <div className="collapsible-section">
                                <button className="collapse-btn" onClick={() => setShowSteps(!showSteps)}>
                                    {showSteps ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    <span>{showSteps ? 'Hide' : 'Show'} agent trace ({message.agentSteps.length} steps)</span>
                                </button>
                                {showSteps && (
                                    <div className="collapse-content agent-steps">
                                        {message.agentSteps.map((step, i) => (
                                            <div key={i} className="agent-step-item">
                                                <div className="agent-step-hdr">
                                                    <span className="step-num">{i + 1}</span>
                                                    <span className="step-tool">{step.tool || 'Thought'}</span>
                                                </div>
                                                {step.input && (
                                                    <div className="step-io input">
                                                        <span className="io-lbl">Input:</span> {step.input.slice(0, 200)}
                                                    </div>
                                                )}
                                                {step.output && (
                                                    <div className="step-io output">
                                                        <span className="io-lbl">Output:</span> {step.output.slice(0, 300)}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                        {hasMore && onLoadMore && (
                            <div className="pagination-bar glass-panel-sub">
                                <div className="pagination-info">
                                    <FileText size={14} />
                                    <span>
                                        <strong>{message.pagination.total_count}</strong> results · page {message.pagination.page}
                                    </span>
                                </div>
                                <button
                                    className="btn-primary-sm"
                                    onClick={() => onLoadMore(message.originalQuestion, message.pagination.page)}
                                >
                                    Load More Docs
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
