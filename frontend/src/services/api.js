const BASE_URL = '/api/v1';
async function request(path, options = {}) {
    const response = await fetch(`${BASE_URL}${path}`, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(err.detail || err.error || `HTTP ${response.status}`);
    }
    return response.json();
}
export async function sendQuery(question, sessionId, opts = {}) {
    return request('/query', {
        method: 'POST',
        body: JSON.stringify({
            question,
            session_id: sessionId,
            page: opts.page || 1,
            page_size: opts.pageSize || 10,
            force_type: opts.forceType || null,
        }),
    });
}
export async function vectorSearch(query, target = 'papers', opts = {}) {
    return request('/search/vector', {
        method: 'POST',
        body: JSON.stringify({
            query,
            target,
            top_k: opts.topK || 10,
            threshold: opts.threshold || 0.7,
            expand_query: opts.expand !== false,
        }),
    });
}
export async function getRecommendations(query, strategy = 'content_based', opts = {}) {
    return request('/recommend', {
        method: 'POST',
        body: JSON.stringify({
            query,
            strategy,
            top_k: opts.topK || 5,
            since_year: opts.sinceYear || 2018,
        }),
    });
}
export async function createNewSession() {
    return request('/session/new', { method: 'POST' });
}
export async function getSession(sessionId) {
    return request(`/session/${sessionId}`);
}
export async function deleteSession(sessionId) {
    return request(`/session/${sessionId}`, { method: 'DELETE' });
}
export async function listSessions() {
    return request('/sessions');
}
export async function getHealth() {
    return request('/health');
}
export async function getSchema() {
    return request('/schema');
}
export async function getSuggestions() {
    return request('/suggestions');
}
export async function getCacheStats() {
    return request('/cache/stats');
}
export async function clearCache() {
    return request('/cache', { method: 'DELETE' });
}
