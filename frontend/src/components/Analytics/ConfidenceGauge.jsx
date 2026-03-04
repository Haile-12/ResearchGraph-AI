import React, { useState } from 'react';
import { formatConfidence } from '../../utils/formatters';
export default function ConfidenceGauge({ score, issues = [], cypher = '', retries = 0 }) {
    const [showCypher, setShowCypher] = useState(false);
    const { label, color, bgColor } = formatConfidence(score);
    const width = `${Math.round(score * 100)}%`;
    return (
        <div className="confidence-bar-container">
            <div className="confidence-bar-label">
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span style={{ color }}>●</span>
                    Query Confidence
                    {retries > 0 && (
                        <span className="badge badge-orange" style={{ fontSize: '0.65rem' }}>
                            {retries} retry{retries > 1 ? 's' : ''}
                        </span>
                    )}
                </span>
                <span style={{ color, fontWeight: 700 }}>{label}</span>
            </div>
            <div className="confidence-bar-track">
                <div
                    className="confidence-bar-fill"
                    style={{ width, background: color }}
                />
            </div>
            {issues.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                    {issues.slice(0, 3).map((issue, i) => (
                        <div key={i} style={{
                            fontSize: '0.72rem', color: '#f97316',
                            display: 'flex', alignItems: 'flex-start', gap: '0.3rem',
                            marginTop: '0.25rem',
                        }}>
                            <span>⚠</span><span>{issue}</span>
                        </div>
                    ))}
                </div>
            )}
            {cypher && (
                <>
                    <button className="explainer-toggle" onClick={() => setShowCypher(v => !v)}>
                        {showCypher ? '▲ Hide' : '▼ Show'} Cypher query
                    </button>
                    {showCypher && (
                        <pre style={{
                            marginTop: '0.5rem',
                            background: '#1e293b',
                            color: '#e2e8f0',
                            padding: '0.75rem',
                            borderRadius: '8px',
                            fontSize: '0.75rem',
                            overflowX: 'auto',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                        }}>
                            {cypher}
                        </pre>
                    )}
                </>
            )}
        </div>
    );
}
