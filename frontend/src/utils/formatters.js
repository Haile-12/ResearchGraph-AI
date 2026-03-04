export function formatConfidence(score) {
    const pct = Math.round(score * 100);
    if (score >= 0.85) return { label: `${pct}%`, color: '#10b981', bgColor: '#f0fdf4' };
    if (score >= 0.70) return { label: `${pct}%`, color: '#3b82f6', bgColor: '#eff6ff' };
    if (score >= 0.40) return { label: `${pct}%`, color: '#f97316', bgColor: '#fff7ed' };
    return { label: `${pct}%`, color: '#ef4444', bgColor: '#fef2f2' };
}
export function formatQueryType(type) {
    const map = {
        GRAPH_TRAVERSAL: { label: 'Graph Traversal', icon: '🔗', color: '#3b82f6' },
        VECTOR_SIMILARITY: { label: 'Semantic Search', icon: '🔍', color: '#8b5cf6' },
        HYBRID: { label: 'Hybrid', icon: '⚡', color: '#f97316' },
        AGENT_COMPLEX: { label: 'AI Agent', icon: '🤖', color: '#10b981' },
        AMBIGUOUS: { label: 'Clarification', icon: '❓', color: '#64748b' },
    };
    return map[type] || { label: type, icon: '📊', color: '#64748b' };
}
export function formatDuration(ms) {
    if (!ms) return '';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}
export function formatRelativeTime(date) {
    const d = new Date(date);
    const now = new Date();
    const secs = Math.floor((now - d) / 1000);
    if (secs < 60) return 'just now';
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
    return d.toLocaleDateString();
}
export function truncate(str, maxLen = 80) {
    if (!str) return '';
    if (str.length <= maxLen) return str;
    return str.slice(0, maxLen - 3) + '…';
}
export function formatSessionName(sessionId) {
    return `New Chat`;
}
export function similarityColor(score) {
    if (score >= 0.9) return '#10b981';
    if (score >= 0.8) return '#3b82f6';
    if (score >= 0.7) return '#f97316';
    return '#ef4444';
}
